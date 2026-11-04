#!/usr/bin/env bash
# Install script for Galaxy S22+ Toolkit Skills
# This installs phone-lib and all 6 ZCode skills in the correct dependency order

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_ROOT="${PROJECT_ROOT}/../.zcode/skills"
PHONE_LIB_ROOT="${PROJECT_ROOT}/../phone-lib"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Galaxy S22+ Toolkit Skills Installer  ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to install a package in development mode
install_package() {
    local name="$1"
    local path="$2"
    
    echo -e "${YELLOW}Installing ${name}...${NC}"
    if [[ -d "${path}" && -f "${path}/pyproject.toml" ]]; then
        cd "${path}"
        # OneDrive-synced trees get the read-only attribute re-applied, which
        # breaks setuptools' egg-info writes - force files writable first
        find . -type f -exec chmod u+w {} + 2>/dev/null || true
        if pip install -e . --quiet; then
            echo -e "${GREEN}  ✓ ${name} installed successfully${NC}"
        else
            echo -e "${RED}  ✗ Failed to install ${name}${NC}"
            return 1
        fi
    else
        echo -e "${RED}  ✗ Package directory not found: ${path}${NC}"
        return 1
    fi
}

# Step 1: Install phone-lib (foundation)
echo -e "${BLUE}Step 1/8: Installing phone-lib (foundation library)${NC}"
install_package "phone-lib (galaxy-s22-toolkit)" "${PHONE_LIB_ROOT}"
echo ""

# Step 2: Install phone-diagnostics
echo -e "${BLUE}Step 2/8: Installing phone-diagnostics skill${NC}"
install_package "phone-diagnostics" "${SKILLS_ROOT}/phone-diagnostics"
echo ""

# Step 3: Install phone-screen-control
echo -e "${BLUE}Step 3/8: Installing phone-screen-control skill${NC}"
install_package "phone-screen-control" "${SKILLS_ROOT}/phone-screen-control"
echo ""

# Step 4: Install phone-file-transfer
echo -e "${BLUE}Step 4/8: Installing phone-file-transfer skill${NC}"
install_package "phone-file-transfer" "${SKILLS_ROOT}/phone-file-transfer"
echo ""

# Step 5: Install phone-logcat
echo -e "${BLUE}Step 5/8: Installing phone-logcat skill${NC}"
install_package "phone-logcat" "${SKILLS_ROOT}/phone-logcat"
echo ""

# Step 6: Install phone-app-manager
echo -e "${BLUE}Step 6/8: Installing phone-app-manager skill${NC}"
install_package "phone-app-manager" "${SKILLS_ROOT}/phone-app-manager"
echo ""

# Step 7: Install phone-root (rooting support)
echo -e "${BLUE}Step 7/8: Installing phone-root (rooting support)${NC}"
install_package "phone-root" "${PROJECT_ROOT}/../rooting"
echo ""

# Step 8: Install phone-repair (approved repair actions)
echo -e "${BLUE}Step 8/8: Installing phone-repair skill${NC}"
install_package "phone-repair" "${SKILLS_ROOT}/phone-repair"
echo ""

# Verify all CLI commands are available
echo -e "${BLUE}Verifying CLI commands...${NC}"
COMMANDS=("phone-diagnostics" "phone-screen-control" "phone-file-transfer" "phone-logcat" "phone-app-manager" "phone-root" "phone-repair")
ALL_OK=true

for cmd in "${COMMANDS[@]}"; do
    if command -v "${cmd}" &> /dev/null; then
        echo -e "${GREEN}  ✓ ${cmd} is available${NC}"
    else
        echo -e "${RED}  ✗ ${cmd} NOT found${NC}"
        ALL_OK=false
    fi
done

echo ""
if [[ "${ALL_OK}" == "true" ]]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  All skills installed successfully!    ${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Available commands:"
    echo "  phone-diagnostics   - Full device health diagnostics"
    echo "  phone-screen-control - Screen capture, recording, input"
    echo "  phone-file-transfer  - Pull/push files with progress"
    echo "  phone-logcat         - Stream/filter logcat logs"
    echo "  phone-app-manager    - Manage apps (list, clear, uninstall)"
    echo "  phone-repair         - Approved repair actions with history"
    echo ""
    echo "Quick test:"
    echo "  phone-diagnostics device"
    echo "  phone-screen-control display-info"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  Some commands failed to install       ${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi