import os
import json
import threading
import urllib.request
import urllib.error
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk, Gedit, Gdk

# -------------------------
# Plugin paths
# -------------------------
PLUGIN_DIR = os.path.dirname(__file__)
ROOT_DIR = PLUGIN_DIR

# -------------------------
# Read configuration
# -------------------------
CONFIG_FILE = os.path.join(os.path.dirname(PLUGIN_DIR), "hello-gpt-config.json")
DEFAULT_CONFIG = {
    "active_provider": "openai",
    "openai": {"api_key": "", "model": "gpt-4o-mini"},
    "gemini": {"api_key": "", "model": "gemini-2.5-flash"}
}

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r") as f:
            CONFIG = json.load(f)
    except Exception:
        CONFIG = DEFAULT_CONFIG
else:
    CONFIG = DEFAULT_CONFIG

ACTIVE_PROVIDER = CONFIG.get("active_provider", "openai").lower()
OPENAI_CONFIG = CONFIG.get("openai", {})
GEMINI_CONFIG = CONFIG.get("gemini", {})

# -------------------------
# API Functions using urllib
# -------------------------
def openai_chat_stream(api_key, model, message, callback):
    """
    Calls the OpenAI Chat Completions API with streaming output.
    """
    if not api_key:
        callback("error", "OpenAI API key is missing")
        return

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": True,
            "temperature": 0.7
        }).encode('utf-8'),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    )
    
    try:
        response = urllib.request.urlopen(req)
        buffer = b""
        
        # Read the stream chunk by chunk and parse NDJSON (data: ...)
        while True:
            chunk = response.read(1)
            if not chunk:
                break
            buffer += chunk
            if buffer.endswith(b'\n'):
                line = buffer.decode('utf-8').strip()
                buffer = b""
                if line.startswith('data: ') and line != 'data: [DONE]':
                    try:
                        data = json.loads(line[6:])  # Strip 'data: ' prefix
                        content = data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if content:
                            callback("text", content)
                    except:
                        pass
        callback("done", None)

    except urllib.error.HTTPError as e:
        error_msg = f"OpenAI HTTP Error: {e.code} - {e.reason}"
        try:
            error_body = e.read().decode()
            error_msg += f"\nResponse: {error_body}"
        except:
            pass
        callback("error", error_msg)
    except urllib.error.URLError as e:
        callback("error", f"OpenAI URL Error: {e.reason}")
    except Exception as e:
        callback("error", f"An unexpected OpenAI error occurred: {e}")

def gemini_chat_stream(api_key, model, message, callback):
    """
    Calls the Gemini API with streaming using the correct endpoint and format.
    """
    if not api_key:
        callback("error", "Gemini API key is missing")
        return

    try:
        # Use the correct streaming endpoint
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}"
        
        req = urllib.request.Request(
            url,
            data=json.dumps({
                "contents": [{
                    "parts": [{"text": message}]
                }],
                "generationConfig": {
                    "temperature": 0.7
                }
            }).encode('utf-8'),
            headers={
                "Content-Type": "application/json"
            }
        )
        
        response = urllib.request.urlopen(req)
        buffer = b""
        
        # Read the Server-Sent Events (SSE) stream
        while True:
            chunk = response.read(1)
            if not chunk:
                break
            buffer += chunk
            
            # Process complete lines
            if buffer.endswith(b'\n'):
                line = buffer.decode('utf-8').strip()
                buffer = b""
                
                # Skip empty lines and event markers
                if not line or line.startswith(':'):
                    continue
                    
                # Process data lines
                if line.startswith('data: '):
                    data_str = line[6:]  # Remove 'data: ' prefix
                    if data_str == '[DONE]':
                        break
                        
                    try:
                        data = json.loads(data_str)
                        
                        # Extract text from Gemini response
                        if 'candidates' in data and data['candidates']:
                            candidate = data['candidates'][0]
                            if 'content' in candidate and 'parts' in candidate['content']:
                                for part in candidate['content']['parts']:
                                    if 'text' in part:
                                        callback("text", part['text'])
                            
                            # Check for errors or blocks
                            finish_reason = candidate.get('finishReason')
                            if finish_reason and finish_reason != 'STOP':
                                if finish_reason == 'SAFETY':
                                    callback("error", "Gemini: Response blocked by safety filters")
                                elif finish_reason == 'OTHER':
                                    callback("error", "Gemini: Response terminated unexpectedly")
                                elif finish_reason == 'MAX_TOKENS':
                                    callback("error", "Gemini: Response exceeded maximum token limit")
                            
                            # Check safety ratings
                            safety_ratings = candidate.get('safetyRatings', [])
                            blocked = False
                            for rating in safety_ratings:
                                if rating.get('probability') in ['HIGH', 'MEDIUM']:
                                    blocked = True
                                    break
                            if blocked:
                                callback("error", "Gemini: Response blocked due to safety concerns")
                                
                    except json.JSONDecodeError as e:
                        # Skip invalid JSON lines
                        continue
                    except Exception as e:
                        callback("error", f"Gemini parsing error: {e}")
        
        callback("done", None)

    except urllib.error.HTTPError as e:
        error_msg = f"Gemini HTTP Error: {e.code} - {e.reason}"
        try:
            error_body = e.read().decode()
            error_data = json.loads(error_body)
            if 'error' in error_data:
                error_msg += f"\nDetails: {error_data['error'].get('message', 'Unknown error')}"
            else:
                error_msg += f"\nResponse: {error_body}"
        except:
            pass
        callback("error", error_msg)
    except urllib.error.URLError as e:
        callback("error", f"Gemini URL Error: {e.reason}")
    except Exception as e:
        callback("error", f"An unexpected Gemini error occurred: {e}")

# -------------------------
# Plugin class
# -------------------------
class HelloGPTPlugin(GObject.Object, Gedit.WindowActivatable):
    __gtype_name__ = "HelloGPTPlugin"
    window = GObject.Property(type=Gedit.Window)

    def __init__(self):
        super().__init__()
        self.handler_id = None

    def do_activate(self):
        self.handler_id = self.window.connect("key-press-event", self.on_key_press)

    def do_deactivate(self):
        if self.handler_id:
            self.window.disconnect(self.handler_id)
            self.handler_id = None

    def do_update_state(self):
        pass

    # -------------------------
    # Key handling
    # -------------------------
    def on_key_press(self, widget, event):
        # Alt+G: stream text
        if event.keyval == Gdk.KEY_g and event.state & Gdk.ModifierType.MOD1_MASK:
            doc = self.window.get_active_document()
            if doc:
                start, end = doc.get_bounds()
                text = doc.get_text(start, end, True)
                threading.Thread(target=self.stream_to_doc, args=(doc, text), daemon=True).start()
            return True

        # Alt+C: open config window
        if event.keyval == Gdk.KEY_c and event.state & Gdk.ModifierType.MOD1_MASK:
            GObject.idle_add(self.open_config_window)
            return True

        return False

    # -------------------------
    # Streaming logic
    # -------------------------
    def stream_to_doc(self, doc, text):
        GObject.idle_add(self.append_to_doc, doc, "\n\n\n")

        def callback(event_type, data):
            if event_type == "text":
                GObject.idle_add(self.append_to_doc, doc, data)
            elif event_type == "error":
                GObject.idle_add(self.show_error, data)
            # "done" event doesn't need any action

        if ACTIVE_PROVIDER == "openai":
            api_key = OPENAI_CONFIG.get("api_key")
            model = OPENAI_CONFIG.get("model", "gpt-3.5-turbo")
            openai_chat_stream(api_key, model, text, callback)

        elif ACTIVE_PROVIDER == "gemini":
            api_key = GEMINI_CONFIG.get("api_key")
            model = GEMINI_CONFIG.get("model", "gemini-2.0-flash-exp")
            gemini_chat_stream(api_key, model, text, callback)
        else:
            GObject.idle_add(self.show_error, f"Unknown GPT provider: {ACTIVE_PROVIDER}")

    # -------------------------
    # Configuration UI
    # -------------------------
    def open_config_window(self):
        global ACTIVE_PROVIDER

        dialog = Gtk.Dialog(
            title="GPT Plugin Configuration",
            transient_for=self.window,
            flags=0,
        )
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                        "Update", Gtk.ResponseType.OK)
        dialog.set_default_size(700, 400)

        header = Gtk.HeaderBar()
        header.set_show_close_button(False)
        header.set_title("GPT Plugin Configuration")
        
        cs_label = Gtk.Label(label="CS@CUSAT")
        cs_label.get_style_context().add_class("dim-label")
        cs_label.set_margin_end(10)
        header.pack_end(cs_label)
        
        dialog.set_titlebar(header)

        content_area = dialog.get_content_area()
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(15)
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)

        main_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_area.pack_start(main_container, True, True, 0)

        content_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        main_container.pack_start(content_vbox, True, True, 0)

        # Active Provider combo
        active_label = Gtk.Label(label="Select Active GPT Provider:")
        active_label.set_halign(Gtk.Align.START)
        active_combo = Gtk.ComboBoxText()
        active_combo.append_text("openai")
        active_combo.append_text("gemini")
        active_combo.set_active(0 if ACTIVE_PROVIDER == "openai" else 1)

        content_vbox.pack_start(active_label, False, False, 0)
        content_vbox.pack_start(active_combo, False, False, 0)

        # Horizontal box for OpenAI and Gemini
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        content_vbox.pack_start(hbox, True, True, 0)

        # -------------------------
        # OpenAI Frame
        # -------------------------
        openai_frame = Gtk.Frame(label="OpenAI Configuration")
        openai_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        openai_frame.set_margin_top(5)
        openai_frame.set_margin_bottom(5)
        openai_frame.set_margin_start(5)
        openai_frame.set_margin_end(5)
        openai_frame.get_style_context().add_class("config-frame")

        openai_grid = Gtk.Grid(column_spacing=10, row_spacing=5, margin=10)
        openai_frame.add(openai_grid)

        openai_grid.attach(Gtk.Label(label="Model:"), 0, 0, 1, 1)
        openai_model_entry = Gtk.Entry()
        openai_model_entry.set_text(OPENAI_CONFIG.get("model", "gpt-3.5-turbo"))
        openai_model_entry.set_placeholder_text("e.g., gpt-3.5-turbo, gpt-4")
        openai_grid.attach(openai_model_entry, 1, 0, 1, 1)

        openai_grid.attach(Gtk.Label(label="API Key:"), 0, 1, 1, 1)
        openai_api_entry = Gtk.Entry()
        openai_api_entry.set_text(OPENAI_CONFIG.get("api_key", ""))
        openai_api_entry.set_placeholder_text("Your OpenAI API Key")
        openai_grid.attach(openai_api_entry, 1, 1, 1, 1)

        hbox.pack_start(openai_frame, True, True, 0)

        # -------------------------
        # Gemini Frame
        # -------------------------
        gemini_frame = Gtk.Frame(label="Gemini Configuration")
        gemini_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        gemini_frame.set_margin_top(5)
        gemini_frame.set_margin_bottom(5)
        gemini_frame.set_margin_start(5)
        gemini_frame.set_margin_end(5)
        gemini_frame.get_style_context().add_class("config-frame")

        gemini_grid = Gtk.Grid(column_spacing=10, row_spacing=5, margin=10)
        gemini_frame.add(gemini_grid)

        gemini_grid.attach(Gtk.Label(label="Model:"), 0, 0, 1, 1)
        gemini_model_entry = Gtk.Entry()
        gemini_model_entry.set_text(GEMINI_CONFIG.get("model", "gemini-2.0-flash-exp"))
        gemini_model_entry.set_placeholder_text("e.g., gemini-2.0-flash-exp, gemini-1.5-flash")
        openai_grid.attach(openai_api_entry, 1, 1, 1, 1)

        gemini_grid.attach(Gtk.Label(label="API Key:"), 0, 1, 1, 1)
        gemini_api_entry = Gtk.Entry()
        gemini_api_entry.set_text(GEMINI_CONFIG.get("api_key", ""))
        gemini_api_entry.set_placeholder_text("Your Gemini API Key")
        gemini_grid.attach(gemini_api_entry, 1, 1, 1, 1)

        hbox.pack_start(gemini_frame, True, True, 0)

        spacer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        spacer.set_size_request(-1, 20)
        main_container.pack_start(spacer, False, False, 0)

        # Add CSS styling for frames
        css_provider = Gtk.CssProvider()
        css = b"""
        .config-frame {
            border-radius: 8px;
            border-width: 1px;
        }
        .active-frame {
            border: none;
            box-shadow: 0 4px 0 rgba(0, 0, 0, 0.3);
        }

        .active-frame > label {
            font-weight: bold;
            color: inherit;
        }
        """
        css_provider.load_from_data(css)
        style_context = dialog.get_style_context()
        style_context.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Highlight the active provider
        def highlight_active(provider):
            if provider == "openai":
                openai_frame.get_style_context().add_class("active-frame")
                gemini_frame.get_style_context().remove_class("active-frame")
            else:
                gemini_frame.get_style_context().add_class("active-frame")
                openai_frame.get_style_context().remove_class("active-frame")

        highlight_active(ACTIVE_PROVIDER)

        # Update highlight when combo changes
        def on_active_changed(combo):
            highlight_active(combo.get_active_text())

        active_combo.connect("changed", on_active_changed)

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            # Update active provider
            ACTIVE_PROVIDER = active_combo.get_active_text()
            CONFIG["active_provider"] = ACTIVE_PROVIDER

            # Update OpenAI config
            CONFIG["openai"]["model"] = openai_model_entry.get_text()
            CONFIG["openai"]["api_key"] = openai_api_entry.get_text()

            # Update Gemini config
            CONFIG["gemini"]["model"] = gemini_model_entry.get_text()
            CONFIG["gemini"]["api_key"] = gemini_api_entry.get_text()

            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(CONFIG, f, indent=2)
            except Exception:
                pass

        dialog.destroy()

    # -------------------------
    # Gtk helpers
    # -------------------------
    def append_to_doc(self, doc, text):
        end_iter = doc.get_end_iter()
        doc.insert(end_iter, text)

    def show_error(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Error contacting GPT API"
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()