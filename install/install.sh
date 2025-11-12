#!/usr/bin/env bash

# --------------------------------------------
# Hello-GPT Gedit Plugin Installer
# --------------------------------------------

PLUGIN_NAME="hello-gpt"
PLUGIN_URL="https://github.com/4n54n/Hello-GPT/raw/refs/heads/main/install/hello-gpt.zip"
PLUGIN_DIR="$HOME/.local/share/gedit/plugins"
OPENAI_DIR="$PLUGIN_DIR/openai-gpt-core"
GOOGLE_DIR="$PLUGIN_DIR/google"

GREEN="\e[32m"
YELLOW="\e[33m"
BLUE="\e[34m"
BOLD="\e[1m"
RESET="\e[0m"

echo -e "${BLUE}${BOLD}--- Hello-GPT Gedit Plugin Installer ---${RESET}\n"

# 1. Check Gedit
if ! command -v gedit &> /dev/null; then
    echo -e "${YELLOW}Gedit is not installed. Please install Gedit and retry.${RESET}"
    exit 1
fi
echo -e "${GREEN}✔ Gedit found${RESET}"

# 2. Ensure plugin directory
if [ ! -d "$PLUGIN_DIR" ]; then
    mkdir -p "$PLUGIN_DIR"
    echo -e "${GREEN}✔ Created plugin directory at $PLUGIN_DIR${RESET}"
else
    echo -e "${GREEN}✔ Plugin directory exists${RESET}"
fi

# 3. Download the plugin
TMP_ZIP=$(mktemp /tmp/${PLUGIN_NAME}.XXXX.zip)
echo -e "${BLUE}Downloading ${PLUGIN_NAME} plugin...${RESET}"

if command -v wget >/dev/null 2>&1; then
    wget -O "$TMP_ZIP" "$PLUGIN_URL" || { echo -e "${YELLOW}Failed to download plugin with wget.${RESET}"; exit 1; }
elif command -v curl >/dev/null 2>&1; then
    curl -L -o "$TMP_ZIP" "$PLUGIN_URL" || { echo -e "${YELLOW}Failed to download plugin with curl.${RESET}"; exit 1; }
else
    echo -e "${YELLOW}Neither wget nor curl is installed. Please install one of them and retry.${RESET}"
    exit 1
fi

echo -e "${GREEN}✔ Downloaded plugin${RESET}"

# 4. Install plugin
echo -e "${BLUE}Installing plugin...${RESET}"
unzip -o "$TMP_ZIP" -d "$PLUGIN_DIR" &> /dev/null
rm "$TMP_ZIP"
echo -e "${GREEN}✔ Plugin installed to $PLUGIN_DIR${RESET}"

# --------------------------------------------
# 5. Update required Python libraries
# --------------------------------------------
echo -e "\n${BLUE}${BOLD}Updating Python libraries via pip...${RESET}"

# Google GenAI
echo -e "${BLUE}Updating Google GenAI...${RESET}"
rm -rf "$GOOGLE_DIR"/*
pip install --upgrade google-genai -t "$GOOGLE_DIR"

# OpenAI GPT Core
echo -e "${BLUE}Updating OpenAI GPT Core...${RESET}"
rm -rf "$OPENAI_DIR"/*
pip install --upgrade openai -t "$OPENAI_DIR"

echo -e "${GREEN}✔ Library update completed!${RESET}"
# --------------------------------------------

# 6. Activate plugin via gsettings
echo -e "\n${BLUE}Activating plugin...${RESET}"
current=$(gsettings get org.gnome.gedit.plugins active-plugins)

if echo "$current" | grep -q "'$PLUGIN_NAME'"; then
    echo -e "${GREEN}✔ Plugin already activated${RESET}"
else
    if [ "$current" = "@as []" ] || [ "$current" = "[]" ]; then
        new="['$PLUGIN_NAME']"
    else
        new="${current%]*}, '$PLUGIN_NAME']"
    fi
    gsettings set org.gnome.gedit.plugins active-plugins "$new"
    echo -e "${GREEN}✔ Plugin activated${RESET}"
fi

# 7. Launch Gedit
echo -e "${BLUE}Launching Gedit...${RESET}"
nohup gedit >/dev/null 2>&1 &

echo -e "\n${BOLD}${GREEN}Successfully activated ${PLUGIN_NAME} plugin!${RESET}"
echo -e "${BOLD}${YELLOW}Use Alt + C to configure and Alt + G to generate a response.${RESET}"
