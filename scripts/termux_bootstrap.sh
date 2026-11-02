#!/bin/bash
#
# Termux Bootstrap Script for Galaxy S22+
# Installs essential packages and configures Termux environment
#
# This script should be run AFTER installing Termux from setup_termux.sh
#
# Usage:
#   adb shell "curl -sL https://raw.githubusercontent.com/your-repo/termux_bootstrap.sh | bash"
#   OR upload and run locally in Termux:
#
# Required packages:
#   - python (for phone-lib)
#   - git (for version control)
#   - openssh (for SSH access)
#   - termux-api (for device API access)
#   - zsh (better shell, optional)
#   - tmux (terminal multiplexer, optional)
#

set -e

echo "=============================================="
echo "   Termux Bootstrap for Galaxy S22+"
echo "=============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if running in Termux
if [ -z "$PREFIX" ]; then
    echo -e "${RED}Error: This script must be run inside Termux.${NC}"
    echo "Please run 'adb shell' and then 'cd /data/data/com.termux/files/usr && bash'"
    exit 1
fi

echo -e "${BLUE}Starting package update...${NC}"
pkg update -y && pkg upgrade -y

echo ""
echo -e "${YELLOW}Installing core packages...${NC}"
pkg install -y \
    python \
    python-pip \
    git \
    openssh \
    curl \
    wget \
    proot-distro \
    zstd

echo ""
echo -e "${YELLOW}Installing Termux:API (if available)...${NC}"
/pkg list-packages | grep -q termux-api && {
    pkg install -y termux-api
    echo -e "${GREEN}Termux:API installed${NC}"
} || {
    echo -e "${YELLOW}Termux:API not available (not installed from Play Store)${NC}"
    echo "Install 'Termux:API' separately from Play Store or F-Droid for:"
    echo "  - Battery status"
    echo "  - Location"
    echo "  - Sensors data"
    echo "  - SMS handling"
}

# Install optional but useful packages
echo ""
echo -e "${YELLOW}Installing optional packages...${NC}"
pkg install -y \
    tmux \
    zsh \
    htop \
    tree \
    jq \
    neofetch \
    vim \
    rsync

# Configure SSH (optional but useful)
echo ""
echo -e "${YELLOW}Configuring SSH server...${NC}"
mkdir -p "$HOME/.ssh"
sshd
echo -e "${GREEN}SSH server started on port 8022${NC}"
echo "Connect with: ssh -p 8022 u0_a$(id -u)@<device-ip>"

# Install Python packages
echo ""
echo -e "${YELLOW}Installing Python packages...${NC}"
pip install --upgrade pip

# Install phone-lib from local path or PyPI
if [ -d "/sdcard/Android/data/com.termux/files/home/phone-lib" ]; then
    echo "Installing phone-lib from local directory..."
    cd /sdcard/Android/data/com.termux/files/home/phone-lib
    pip install -e .
else
    echo "Installing phone-lib from PyPI..."
    pip install galaxy-s22-toolkit || echo -e "${YELLOW}pip install failed, you can install phone-lib manually${NC}"
fi

# Set up dotfiles
echo ""
echo -e "${YELLOW}Setting up environment...${NC}"

# Create .bash_profile if it doesn't exist
if [ ! -f "$HOME/.bash_profile" ]; then
    cat > "$HOME/.bash_profile" << 'EOF'
# Termux .bash_profile
export PATH="$PATH:$HOME/.local/bin"
export TERM=xterm-256color

# Alias for quick navigation
alias phone='cd ~/phone-lib'
alias logs='cd ~/logs'

# Function to list packages
pkg-list() {
    pkg list-installed
}

# Function to check ADB
check-adb() {
    adb devices
}
EOF
fi

# Configure zsh as default
if [ -f "$PREFIX/bin/zsh" ]; then
    chsh -s zsh
    echo -e "${GREEN}Default shell changed to zsh${NC}"
fi

# Create useful directories
mkdir -p "$HOME/phone-lib"
mkdir -p "$HOME/logs"
mkdir -p "$HOME/bin"
mkdir -p "$HOME/.termux/boot"

echo ""
echo "=============================================="
echo "   Bootstrap Complete!"
echo "=============================================="
echo ""
echo -e "${BLUE}Installed packages:${NC}"
pkg list-installed | head -20
echo "..."

echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Run: neofetch (to see system info)"
echo "  2. Run: adb connect <device-ip>:5555 (from host)"
echo "  3. Use: tmux new -s session-name (for persistent sessions)"
echo ""
echo -e "${BLUE}To enable wireless ADB on device:${NC}"
echo "  In Termux: termux-wifi-enable"
echo "  Then on host: adb connect \$(termux-wifi --format json | jq -r '.ip')"
echo ""

exit 0