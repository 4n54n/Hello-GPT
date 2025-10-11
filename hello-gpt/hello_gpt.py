import os
import sys
import json
import threading
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk, Gedit, Gdk

# -------------------------
# Plugin paths
# -------------------------
PLUGIN_DIR = os.path.dirname(__file__)
ROOT_DIR = PLUGIN_DIR

OPENAI_DIR = os.path.join(PLUGIN_DIR, "openai-gpt-core")
GEMINI_DIR = os.path.join(PLUGIN_DIR, "google")

# Make vendored SDKs importable
for path in [OPENAI_DIR, GEMINI_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Import vendored SDKs
try:
    import openai
except ImportError:
    openai = None

try:
    import google.genai as genai
except ImportError:
    genai = None

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
# Plugin class
# -------------------------
class HelloGPTPlugin(GObject.Object, Gedit.WindowActivatable):
    __gtype_name__ = "HelloGPTPlugin"
    window = GObject.Property(type=Gedit.Window)

    def __init__(self):
        super().__init__()
        self.handler_id = None
        self.gemini_client = None
        if ACTIVE_PROVIDER == "gemini" and genai:
            api_key = GEMINI_CONFIG.get("api_key")
            try:
                self.gemini_client = genai.Client(api_key=api_key)
            except Exception:
                self.gemini_client = None

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

        if ACTIVE_PROVIDER == "openai":
            try:
                api_key = OPENAI_CONFIG.get("api_key")
                model = OPENAI_CONFIG.get("model", "gpt-4o-mini")

                # Check OpenAI module import
                if 'openai' not in globals() or openai is None:
                    raise ImportError("OpenAI module not imported or unavailable")

                # Check API key presence
                if not api_key:
                    raise ValueError("OpenAI API key is missing in OPENAI_CONFIG")

                # Try initializing or testing key
                openai.api_key = api_key
                # Optional: make a simple test request to validate key (comment out if not needed)
                # openai.models.list()

            except Exception as e:
                # Capture any error and show it in the UI
                error_message = f"OpenAI API initialization failed: {str(e)}"
                GObject.idle_add(self.show_error, error_message)
                return


            openai.api_key = api_key
            try:
                with openai.chat.completions.stream(
                    model=model,
                    messages=[{"role": "user", "content": text}],
                    temperature=0.7
                ) as stream:
                    for event in stream:
                        if getattr(event, "type", "") == "content.delta" and event.delta:
                            GObject.idle_add(self.append_to_doc, doc, event.delta)
            except Exception as e:
                GObject.idle_add(self.show_error, str(e))

        elif ACTIVE_PROVIDER == "gemini":
            model = GEMINI_CONFIG.get("model", "gemini-2.5-flash")
            if not self.gemini_client:
                GObject.idle_add(self.show_error, "Gemini API not available or API key missing")
                return

            try:
                stream = self.gemini_client.models.generate_content_stream(
                    model=model,
                    contents=text
                )
                for chunk in stream:
                    if getattr(chunk, "text", None):
                        GObject.idle_add(self.append_to_doc, doc, chunk.text)
            except Exception as e:
                GObject.idle_add(self.show_error, str(e))
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
        dialog.set_default_size(700, 400)  # Increased height a bit

        header = Gtk.HeaderBar()
        header.set_show_close_button(False)
        header.set_title("GPT Plugin Configuration")
        
        cs_label = Gtk.Label(label="CS@CUSAT")
        cs_label.get_style_context().add_class("dim-label")
        cs_label.set_margin_end(10)
        header.pack_end(cs_label)
        
        # Set the header bar as the title bar of the dialog
        dialog.set_titlebar(header)

        content_area = dialog.get_content_area()
        
        # Add margin to the content area
        content_area.set_margin_top(10)
        content_area.set_margin_bottom(15)  # Increased bottom margin
        content_area.set_margin_start(10)
        content_area.set_margin_end(10)

        # Create a main container with proper spacing
        main_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_area.pack_start(main_container, True, True, 0)

        # Content area for the configuration
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
        openai_model_entry.set_text(OPENAI_CONFIG.get("model", "gpt-4o-mini"))
        openai_model_entry.set_placeholder_text("e.g., gpt-4o-mini")
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
        gemini_model_entry.set_text(GEMINI_CONFIG.get("model", "gemini-2.5-flash"))
        gemini_model_entry.set_placeholder_text("e.g., gemini-2.5-flash")
        gemini_grid.attach(gemini_model_entry, 1, 0, 1, 1)

        gemini_grid.attach(Gtk.Label(label="API Key:"), 0, 1, 1, 1)
        gemini_api_entry = Gtk.Entry()
        gemini_api_entry.set_text(GEMINI_CONFIG.get("api_key", ""))
        gemini_api_entry.set_placeholder_text("Your Gemini API Key")
        gemini_grid.attach(gemini_api_entry, 1, 1, 1, 1)

        hbox.pack_start(gemini_frame, True, True, 0)

        # Add a spacer at the bottom to push content up and create space above buttons
        spacer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        spacer.set_size_request(-1, 20)  # 20 pixels height spacer
        main_container.pack_start(spacer, False, False, 0)

        # Add CSS styling for frames
        css_provider = Gtk.CssProvider()
        css = b"""
        .config-frame {
            border-radius: 8px;
            border-width: 1px;
        }
        .active-frame {
            border: none; /* remove border */
            box-shadow: 0 4px 0 rgba(0, 0, 0, 0.3); /* shadow strictly at bottom */
        }

        .active-frame > label {
            font-weight: bold;
            color: inherit; /* remove specific color */
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

            # Reload Gemini client
            if genai:
                try:
                    self.gemini_client = genai.Client(api_key=CONFIG["gemini"]["api_key"])
                except Exception:
                    self.gemini_client = None

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