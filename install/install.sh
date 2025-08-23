#!/usr/bin/env bash

# --------------------------------------------
# Hello-GPT Gedit Plugin Installer
# --------------------------------------------

PLUGIN_NAME="hello-gpt"
PLUGIN_URL="https://github.com/4n54n/Hello-GPT/raw/refs/heads/main/install/hello-gpt.zip"
PLUGIN_DIR="$HOME/.local/share/gedit/plugins"

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

if [ ! -d "$PLUGIN_DIR" ]; then
    mkdir -p "$PLUGIN_DIR"
    echo -e "${GREEN}✔ Created plugin directory at $PLUGIN_DIR${RESET}"
else
    echo -e "${GREEN}✔ Plugin directory exists${RESET}"
fi

TMP_ZIP=$(mktemp /tmp/${PLUGIN_NAME}.XXXX.zip)
echo -e "${BLUE}Downloading ${PLUGIN_NAME} plugin...${RESET}"

if command -v wget >/dev/null 2>&1; then
    if ! wget -O "$TMP_ZIP" "$PLUGIN_URL"; then
        echo -e "${YELLOW}Failed to download plugin with wget. Please check the URL.${RESET}"
        exit 1
    fi
elif command -v curl >/dev/null 2>&1; then
    if ! curl -L -o "$TMP_ZIP" "$PLUGIN_URL"; then
        echo -e "${YELLOW}Failed to download plugin with curl. Please check the URL.${RESET}"
        exit 1
    fi
else
    echo -e "${YELLOW}Neither wget nor curl is installed. Please install one of them and retry.${RESET}"
    exit 1
fi

echo -e "${GREEN}✔ Downloaded plugin${RESET}"

echo -e "${BLUE}Installing plugin...${RESET}"
unzip -o "$TMP_ZIP" -d "$PLUGIN_DIR" &> /dev/null
rm "$TMP_ZIP"
echo -e "${GREEN}✔ Plugin installed to $PLUGIN_DIR${RESET}"

# 5. Activate plugin via gsettings
echo -e "${BLUE}Activating plugin...${RESET}"
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

echo -e "${BLUE}Launching Gedit...${RESET}"
nohup gedit >/dev/null 2>&1 &

echo -e "\n${BOLD}${GREEN}Successfully activated ${PLUGIN_NAME} plugin!${RESET}"
echo -e "${BOLD}${YELLOW}Use Ctrl + C to configure and Ctrl + G to generate a response.${RESET}"
