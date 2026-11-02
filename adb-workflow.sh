#!/bin/bash
# =============================================================================
# Optimized ADB Workflow for Samsung Galaxy S22+ (SM_S906B) - Bash Version
# Based on Microsoft Learn documentation and Android development best practices
# =============================================================================

# Configuration
DEVICE_SERIAL="RFCTA0AEKZP"
# Auto-detect ADB path (WSL / Git Bash / Linux)
if [[ -f "/mnt/c/Users/tbaltzakis/Android/Sdk/platform-tools/adb" ]]; then
    ADB_PATH="/mnt/c/Users/tbaltzakis/Android/Sdk/platform-tools/adb"
elif [[ -f "${HOME}/Android/Sdk/platform-tools/adb" ]]; then
    ADB_PATH="${HOME}/Android/Sdk/platform-tools/adb"
elif [[ -f "/c/Users/tbaltzakis/Android/Sdk/platform-tools/adb" ]]; then
    ADB_PATH="/c/Users/tbaltzakis/Android/Sdk/platform-tools/adb"
else
    ADB_PATH="adb"  # Fallback to PATH
fi
DEVICE_IP=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# =============================================================================
# CORE FUNCTIONS
# =============================================================================

get_device_ip() {
    $ADB_PATH -s $DEVICE_SERIAL shell "ip -f inet addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1" | tr -d '\r'
}

adb_connect() {
    local ip=${1:-$(get_device_ip)}
    local port=${2:-5555}
    $ADB_PATH tcpip $port
    sleep 2
    $ADB_PATH connect "${ip}:${port}"
    DEVICE_IP=$ip
    echo -e "${GREEN}Connected to ${ip}:${port}${NC}"
}

adb_disconnect() {
    local ip=${1:-$DEVICE_IP}
    $ADB_PATH disconnect "${ip}:5555"
    echo -e "${YELLOW}Disconnected from ${ip}${NC}"
}

adb_devices() {
    $ADB_PATH devices -l
}

# =============================================================================
# APP MANAGEMENT
# =============================================================================

adb_install() {
    local apk_path="$1"
    local replace=false
    local test=false
    local grant=false

    shift
    while [[ $# -gt 0 ]]; do
        case $1 in
            -r|--replace) replace=true ;;
            -t|--test) test=true ;;
            -g|--grant) grant=true ;;
        esac
        shift
    done

    local args=()
    $replace && args+=("-r")
    $test && args+=("-t")
    $grant && args+=("-g")
    args+=("$apk_path")

    $ADB_PATH -s $DEVICE_SERIAL install "${args[@]}"
}

adb_uninstall() {
    local package="$1"
    local keep_data=false
    [[ "$2" == "-k" ]] && keep_data=true

    local args=()
    $keep_data && args+=("-k")
    args+=("$package")

    $ADB_PATH -s $DEVICE_SERIAL uninstall "${args[@]}"
}

adb_list_packages() {
    local filter=""
    local system=false
    local third=false
    local enabled=false
    local disabled=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -s|--system) system=true ;;
            -3|--third-party) third=true ;;
            -e|--enabled) enabled=true ;;
            -d|--disabled) disabled=true ;;
            *) filter="$1" ;;
        esac
        shift
    done

    local args=("shell" "pm" "list" "packages")
    $system && args+=("-s")
    $third && args+=("-3")
    $enabled && args+=("-e")
    $disabled && args+=("-d")

    local output=$($ADB_PATH -s $DEVICE_SERIAL "${args[@]}")
    if [[ -n "$filter" ]]; then
        echo "$output" | grep "$filter"
    else
        echo "$output"
    fi
}

adb_clear_data() {
    $ADB_PATH -s $DEVICE_SERIAL shell pm clear "$1"
}

adb_grant_permissions() {
    local pkg="$1"
    $ADB_PATH -s $DEVICE_SERIAL shell pm grant "$pkg" android.permission.READ_EXTERNAL_STORAGE
    $ADB_PATH -s $DEVICE_SERIAL shell pm grant "$pkg" android.permission.WRITE_EXTERNAL_STORAGE
    $ADB_PATH -s $DEVICE_SERIAL shell pm grant "$pkg" android.permission.CAMERA
    $ADB_PATH -s $DEVICE_SERIAL shell pm grant "$pkg" android.permission.RECORD_AUDIO
    $ADB_PATH -s $DEVICE_SERIAL shell pm grant "$pkg" android.permission.ACCESS_FINE_LOCATION
    $ADB_PATH -s $DEVICE_SERIAL shell pm grant "$pkg" android.permission.ACCESS_COARSE_LOCATION
}

# =============================================================================
# LOGCAT - OPTIMIZED FOR DEVELOPMENT
# =============================================================================

adb_logcat() {
    local filter=""
    local tag=""
    local level="V"
    local color=false
    local time=false
    local thread=false
    local pid=false
    local lines=0

    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--filter) filter="$2"; shift ;;
            -t|--tag) tag="$2"; shift ;;
            -l|--level) level="$2"; shift ;;
            -c|--color) color=true ;;
            -T|--time) time=true ;;
            --thread) thread=true ;;
            --pid) pid=true ;;
            -n|--lines) lines="$2"; shift ;;
        esac
        shift
    done

    local args=("-s" "$DEVICE_SERIAL" "logcat")
    if $color; then
        args+=("-v" "color")
    elif $time; then
        args+=("-v" "time")
    elif $thread; then
        args+=("-v" "threadtime")
    else
        args+=("-v" "brief")
    fi

    if $pid && [[ -n "$filter" ]]; then
        local pid_val=$($ADB_PATH -s $DEVICE_SERIAL shell pidof "$filter" | tr -d '\r')
        if [[ -n "$pid_val" ]]; then
            args+=("--pid=$pid_val")
        fi
    elif [[ -n "$tag" ]]; then
        args+=("${tag}:${level}")
    elif [[ -n "$filter" ]]; then
        args+=("${filter}:${level}")
    else
        args+=("*:${level}")
    fi

    if [[ $lines -gt 0 ]]; then
        args+=("-t" "$lines")
    fi

    $ADB_PATH "${args[@]}"
}

adb_logcat_app() {
    local pkg="$1"
    local level="${2:-V}"
    local lines="${3:-0}"
    local pid=$($ADB_PATH -s $DEVICE_SERIAL shell pidof "$pkg" | tr -d '\r')
    if [[ -n "$pid" ]]; then
        adb_logcat -f "$pkg" -l "$level" -n "$lines" --pid
    fi
}

adb_logcat_errors() {
    adb_logcat -l "E" -n "${1:-100}"
}

adb_logcat_warnings() {
    adb_logcat -l "W" -n "${1:-100}"
}

adb_logcat_crash() {
    adb_logcat -t "AndroidRuntime" -l "E" -n "${1:-50}"
}

# =============================================================================
# FILE TRANSFER
# =============================================================================

adb_push() {
    $ADB_PATH -s $DEVICE_SERIAL push "$1" "$2"
}

adb_pull() {
    local remote="$1"
    local local="${2:-.}"
    $ADB_PATH -s $DEVICE_SERIAL pull "$remote" "$local"
}

# =============================================================================
# SCREENSHOTS & SCREEN RECORDING
# =============================================================================

adb_screenshot() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local remote="/sdcard/screenshot_${timestamp}.png"
    local local="${1:-.}"

    $ADB_PATH -s $DEVICE_SERIAL shell screencap -p "$remote"
    $ADB_PATH -s $DEVICE_SERIAL pull "$remote" "$local"
    $ADB_PATH -s $DEVICE_SERIAL shell rm "$remote"
    echo -e "${GREEN}Screenshot saved to $local${NC}"
}

adb_screenrecord() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local remote="/sdcard/record_${timestamp}.mp4"
    local local="${1:-.}"
    local time_limit="${2:-180}"
    local bitrate="${3:-4000000}"

    echo -e "${YELLOW}Recording for ${time_limit}s... Press Ctrl+C to stop${NC}"
    $ADB_PATH -s $DEVICE_SERIAL shell screenrecord --time-limit "$time_limit" --bit-rate "$bitrate" "$remote" &
    local pid=$!

    trap "kill $pid 2>/dev/null; sleep 1; $ADB_PATH -s $DEVICE_SERIAL pull '$remote' '$local'; $ADB_PATH -s $DEVICE_SERIAL shell rm '$remote'; echo -e '${GREEN}Recording saved to $local${NC}'" INT
    wait $pid
}

# =============================================================================
# SHELL & DEBUGGING
# =============================================================================

adb_shell() {
    if [[ -n "$1" ]]; then
        $ADB_PATH -s $DEVICE_SERIAL shell "$@"
    else
        $ADB_PATH -s $DEVICE_SERIAL shell
    fi
}

adb_getprop() {
    if [[ -n "$1" ]]; then
        $ADB_PATH -s $DEVICE_SERIAL shell getprop "$1"
    else
        $ADB_PATH -s $DEVICE_SERIAL shell getprop
    fi
}

adb_setprop() {
    $ADB_PATH -s $DEVICE_SERIAL shell setprop "$1" "$2"
}

adb_dumpsys() {
    if [[ -n "$1" ]]; then
        $ADB_PATH -s $DEVICE_SERIAL shell dumpsys "$1" "${2:-}"
    else
        $ADB_PATH -s $DEVICE_SERIAL shell dumpsys | grep "DUMP OF SERVICE"
    fi
}

adb_batterystats() { adb_dumpsys batterystats; }
adb_meminfo() { adb_dumpsys meminfo "${1:-}"; }
adb_cpuinfo() { adb_dumpsys cpuinfo; }
adb_activity() { adb_dumpsys activity "${1:-}"; }
adb_package() { adb_dumpsys package "${1:-}"; }

# =============================================================================
# INPUT & UI
# =============================================================================

adb_tap() { $ADB_PATH -s $DEVICE_SERIAL shell input tap "$1" "$2"; }
adb_swipe() { $ADB_PATH -s $DEVICE_SERIAL shell input swipe "$1" "$2" "$3" "$4" "${5:-300}"; }
adb_text() { $ADB_PATH -s $DEVICE_SERIAL shell input text "$1"; }
adb_keyevent() { $ADB_PATH -s $DEVICE_SERIAL shell input keyevent "$1"; }

# =============================================================================
# NETWORK FORWARDING
# =============================================================================

adb_forward() { $ADB_PATH -s $DEVICE_SERIAL forward "tcp:$1" "tcp:$2"; }
adb_forward_remove() { $ADB_PATH -s $DEVICE_SERIAL forward --remove "tcp:$1"; }
adb_forward_list() { $ADB_PATH -s $DEVICE_SERIAL forward --list; }
adb_reverse() { $ADB_PATH -s $DEVICE_SERIAL reverse "tcp:$1" "tcp:$2"; }

# =============================================================================
# DEBUGGING
# =============================================================================

adb_bugreport() {
    local output="${1:-.}"
    local file="bugreport_$(date +%Y%m%d_%H%M%S).zip"
    $ADB_PATH -s $DEVICE_SERIAL bugreport "$output/$file"
    echo -e "${GREEN}Bugreport saved to $output/$file${NC}"
}

# =============================================================================
# APP SHORTCUTS
# =============================================================================

adb_start_app() {
    local pkg="$1"
    local activity="${2:-}"
    if [[ -n "$activity" ]]; then
        $ADB_PATH -s $DEVICE_SERIAL shell am start -n "${pkg}/${activity}"
    else
        $ADB_PATH -s $DEVICE_SERIAL shell monkey -p "$pkg" -c android.intent.category.LAUNCHER 1
    fi
}

adb_stop_app() { $ADB_PATH -s $DEVICE_SERIAL shell am force-stop "$1"; }
adb_restart_app() { adb_stop_app "$1"; sleep 1; adb_start_app "$1" "$2"; }
adb_clear_and_start() { adb_clear_data "$1"; adb_start_app "$1" "$2"; }

# =============================================================================
# WIRELESS SETUP
# =============================================================================

setup_wireless_adb() {
    echo -e "${CYAN}=== Wireless ADB Setup for Samsung Galaxy S22+ ===${NC}"
    echo -e "${GRAY}Device: $DEVICE_SERIAL (SM_S906B)${NC}"

    echo -e "\n${YELLOW}1. Enabling TCP/IP mode on port 5555...${NC}"
    $ADB_PATH -s $DEVICE_SERIAL tcpip 5555
    sleep 2

    echo -e "${YELLOW}2. Getting device IP address...${NC}"
    local ip=$(get_device_ip)
    if [[ -z "$ip" ]]; then
        echo -e "${RED}ERROR: Could not detect IP. Ensure Wi-Fi is on.${NC}"
        return 1
    fi
    echo -e "   ${GREEN}Device IP: $ip${NC}"

    echo -e "${YELLOW}3. Connecting wirelessly...${NC}"
    local result=$($ADB_PATH connect "${ip}:5555")

    if [[ "$result" == *"connected"* ]]; then
        echo -e "\n${GREEN}✅ Wireless ADB connected!${NC}"
        echo -e "${CYAN}   Disconnect USB cable.${NC}"
        DEVICE_IP=$ip
    else
        echo -e "\n${RED}❌ Failed:${NC} $result"
        echo -e "${YELLOW}Troubleshooting:${NC}"
        echo -e "  ${GRAY}- Same Wi-Fi network?${NC}"
        echo -e "  ${GRAY}- adb kill-server && adb start-server${NC}"
        echo -e "  ${GRAY}- Toggle USB debugging${NC}"
        echo -e "  ${GRAY}- Firewall allows port 5555${NC}"
    fi
}

# =============================================================================
# WORKFLOWS
# =============================================================================

workflow_app_debug() { adb_logcat_app "$1" "V" 50; }
workflow_app_install_debug() { adb_install -r -g "$1"; adb_logcat_app "$2" "V"; }
workflow_perf_check() { adb_meminfo "$1"; echo; adb_cpuinfo; echo; adb_batterystats; }

# =============================================================================
# ALIASES
# =============================================================================

alias adbi='adb_install'
alias adbu='adb_uninstall'
alias adbl='adb_list_packages'
alias adblc='adb_logcat'
alias adblce='adb_logcat_errors'
alias adblcw='adb_logcat_warnings'
alias adblcc='adb_logcat_crash'
alias adbs='adb_screenshot'
alias adbsr='adb_screenrecord'
alias adbsh='adb_shell'
alias adbpush='adb_push'
alias adbpull='adb_pull'
alias adbdev='adb_devices'
alias adbconn='adb_connect'
alias adbdis='adb_disconnect'

# =============================================================================
# STARTUP MESSAGE
# =============================================================================

echo -e "\n${CYAN}===========================================${NC}"
echo -e "${CYAN}ADB Workflow loaded for Samsung Galaxy S22+${NC}"
echo -e "${GRAY}Device: $DEVICE_SERIAL${NC}"
echo -e "${CYAN}===========================================${NC}"
echo -e "\n${YELLOW}Quick Commands:${NC}"
echo -e "  ${GRAY}setup_wireless_adb     - One-command wireless setup${NC}"
echo -e "  ${GRAY}adb_connect            - Connect to wireless device${NC}"
echo -e "  ${GRAY}adb_devices            - List connected devices${NC}"
echo -e "  ${GRAY}adb_logcat_app <pkg>   - Filtered logcat for app${NC}"
echo -e "  ${GRAY}adb_screenshot         - Take & pull screenshot${NC}"
echo -e "  ${GRAY}adb_screenrecord       - Record screen (180s default)${NC}"
echo -e "  ${GRAY}adb_install <apk>      - Install with permissions${NC}"
echo -e "  ${GRAY}adb_list_packages -3   - List user-installed apps${NC}"
echo -e "  ${GRAY}workflow_app_debug <pkg> - Full app debugging session${NC}"
echo -e "\n${GRAY}Aliases: adbi, adbu, adbl, adblc, adblce, adblcw, adblcc, adbs, adbsr, adbsh, adbpush, adbpull, adbdev, adbconn, adbdis${NC}"