#!/bin/bash
#
# Termux Installation Script for Galaxy S22+
# This script downloads and installs Termux from F-Droid
#
# Requirements:
# - Android device with Google Play Store or F-Droid
# - ~100MB free storage
#
# Usage:
#   1. Download F-Droid from https://f-droid.org/
#   2. Install F-Droid if not already installed
#   3. Run: adb install termux.apk (if downloading separately)
#   OR use F-Droid app directly
#
# For Galaxy S22+, you can also install from:
#   - Google Play Store: "Termux" by termux
#   - F-Droid: "Termux" package
#

set -e

TERMUX_PKG_NAME="termux"
F-DROID_URL="https://f-droid.org/repos/de.mrapp.termplex_100000.apk"
PLAY_STORE_PKG="com.termux"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "   Termux Installation Script for Galaxy S22+"
echo "=============================================="
echo ""

# Check if adb is available
if ! command -v adb &> /dev/null; then
    echo -e "${RED}Error: adb not found. Please install Android SDK Platform Tools.${NC}"
    echo "Download from: https://developer.android.com/studio/releases/platform-tools"
    exit 1
fi

# Check device connection
echo -e "${YELLOW}Checking device connection...${NC}"
adb devices | grep -q "device" || {
    echo -e "${RED}Error: No device connected. Please connect your Galaxy S22+ via USB.${NC}"
    exit 1
}

# Get connected device serial
DEVICE_SERIAL=$(adb devices | grep "device" | head -1 | cut -f1)
echo -e "${GREEN}Found device: $DEVICE_SERIAL${NC}"

# Check if Termux is already installed
echo -e "${YELLOW}Checking if Termux is installed...${NC}"
if adb shell "pm list packages | grep $PLAY_STORE_PKG" | grep -q "$PLAY_STORE_PKG"; then
    echo -e "${GREEN}Termux is already installed on the device.${NC}"
    echo "To update Termux, run: ./setup_termux.sh --update"
    exit 0
fi

echo -e "${YELLOW}Termux not found. Proceeding with installation...${NC}"
echo ""

# Download Termux APK from F-Droid
DOWNLOAD_DIR="/tmp/termux_install"
mkdir -p "$DOWNLOAD_DIR"

echo -e "${YELLOW}Downloading Termux from F-Droid...${NC}"
wget -q "$F-DROID_URL" -O "$DOWNLOAD_DIR/termux.apk" || {
    echo -e "${RED}Failed to download Termux APK.${NC}"
    echo "Please try one of these alternatives:"
    echo "  1. Install from Google Play Store: Search 'Termux' in Play Store"
    echo "  2. Install from F-Droid: Open F-Droid app, search 'Termux', install"
    exit 1
}

echo -e "${GREEN}Download complete: $DOWNLOAD_DIR/termux.apk${NC}"

# Verify APK
echo -e "${YELLOW}Verifying APK integrity...${NC}"
if command -v apksigner &> /dev/null; then
    apksigner verify "$DOWNLOAD_DIR/termux.apk" && echo -e "${GREEN}APK signature verified${NC}" || echo -e "${YELLOW}Warning: APK signature verification failed (may be normal for F-Droid builds)${NC}"
else
    echo -e "${YELLOW}apksigner not available, skipping signature verification${NC}"
fi

# Install Termux
echo -e "${YELLOW}Installing Termux on device...${NC}"
adb install -r "$DOWNLOAD_DIR/termux.apk" || {
    echo -e "${RED}Installation failed.${NC}"
    echo "Common solutions:"
    echo "  1. Enable 'Install unknown apps' for your browser/file manager"
    echo "  2. Try installing from Play Store instead"
    exit 1
}

echo -e "${GREEN}Termux installed successfully!${NC}"

# Cleanup
rm -rf "$DOWNLOAD_DIR"

# Next steps
echo ""
echo "=============================================="
echo "   Installation Complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "  1. Launch Termux from your app drawer"
echo "  2. Run: pkg update && pkg upgrade"
echo "  3. Run: ./termux_bootstrap.sh to install packages"
echo ""
echo "Optional: To enable Termux:API:"
echo "  1. Install 'Termux:API' from Play Store or F-Droid"
echo "  2. Use: adb install <path-to-termux-api.apk>"
echo ""

exit 0