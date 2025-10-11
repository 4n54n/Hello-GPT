#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Fixing libraries via pip install..."

# Paths
PLUGIN_DIR="$HOME/.local/share/gedit/plugins/hello-gpt"

# --- Google GenAI Plugin ---
echo "Installing Google GenAI..."
rm -rf "$PLUGIN_DIR/google"
mkdir -p "$PLUGIN_DIR/google"
pip install --upgrade google-genai -t "$PLUGIN_DIR/google"

# --- OpenAI GPT Core Plugin ---
echo "Installing OpenAI GPT Core..."
rm -rf "$PLUGIN_DIR/openai-gpt-core"
mkdir -p "$PLUGIN_DIR/openai-gpt-core"
pip install --upgrade openai -t "$PLUGIN_DIR/openai-gpt-core"

echo "Installation completed!"
