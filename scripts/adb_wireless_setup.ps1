# ADB Wireless Setup Script for Galaxy S22+
# One-click setup for wireless ADB debugging
#
# Usage:
#   .\adb_wireless_setup.ps1 [-Enable] [-Disable] [-Status]
#
# Examples:
#   .\adb_wireless_setup.ps1 -Enable    # Enable wireless ADB
#   .\adb_wireless_setup.ps1 -Disable   # Disable wireless ADB
#   .\adb_wireless_setup.ps1 -Status    # Show current status
#

param(
    [switch]$Enable,
    [switch]$Disable,
    [switch]$Status,
    [int]$Port = 5555,
    [switch]$AutoConnect
)

# Colors
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Cyan"
$NC = "White"

function Write-Status {
    param($Message, $Color = $NC)
    Write-Host "  [$Color]$Message" -ForegroundColor $Color
}

function Test-AbdConnection {
    $result = adb devices 2>$null
    return $result -match "device$"
}

function Get-ConnectedDevice {
    param($SerialNumber = "RFCTA0AEKZP")
    $devices = adb devices -l 2>$null
    foreach ($device in $devices) {
        if ($device -match "$SerialNumber\s+device") {
            return $true
        }
    }
    return $false
}

function Get-DeviceWifiIp {
    # Try multiple methods to get WiFi IP
    $ip = adb shell "ip -f inet addr show wlan0" 2>$null | Select-String "inet " | ForEach-Object {
        ($_ -split '\s+')[2].Split("/")[0]
    }

    if (-not $ip) {
        # Fallback: try ip route
        $ip = adb shell "ip route" 2>$null | Select-String "via" | ForEach-Object {
            ($_ -split '\s+')[3]
        }
    }

    if (-not $ip) {
        # Another fallback: use hostname method
        $ip = adb shell "getprop net.hostname" 2>$null
    }

    return $ip
}

function Get-WirelessAdbStatus {
    # Check if ADB over TCP/IP is enabled
    $tcpPort = adb shell "getprop service.adb.tcp.port" 2>$null
    $tcpPortValue = if ($tcpPort -and $tcpPort -ne "-1") { [int]$tcpPort } else { $null }

    # Get WiFi IP
    $wifiIp = Get-DeviceWifiIp

    # Check connected devices - only those connected on wireless port (format: IP:PORT or device)
    $devices = adb devices 2>$null | Select-String ":$Port\s+device" | ForEach-Object {
        $_.Line.Trim()
    }

    # Return as PSCustomObject using Write-Output to avoid parameter binding issues
    Write-Output ([PSCustomObject]@{
        TcpPort = $tcpPortValue
        WifiIp = $wifiIp
        ConnectedDevices = $devices
    })
}

# Main logic
Write-Host ""
Write-Host "=============================================="
Write-Host "   ADB Wireless Setup for Galaxy S22+"
Write-Host "=============================================="
Write-Host ""

# Check if device is connected
if (-not (Test-AbdConnection)) {
    Write-Host "[$Red]No device connected via USB.$NC"
    Write-Host "  Please connect your Galaxy S22+ (RFCTA0AEKZP) via USB and authorize."
    Write-Host ""
    exit 1
}

if (-not (Get-ConnectedDevice)) {
    Write-Host "[$Red]Device RFCTA0AEKZP not found or not authorized.$NC"
    Write-Host "  Check USB debugging is enabled and device is authorized."
    Write-Host ""
    exit 1
}

# Status action
if ($Status) {
    Write-Host "[$Blue]Wireless ADB Status:$NC" -ForegroundColor $Blue
    $adbStatus = Get-WirelessAdbStatus

    if ($adbStatus.TcpPort) {
        Write-Host "  TCP Port: $($adbStatus.TcpPort)"
    } else {
        Write-Host "  TCP Port: Disabled"
    }

    if ($adbStatus.WifiIp) {
        Write-Host "  WiFi IP: $($adbStatus.WifiIp)"
    } else {
        Write-Host "  WiFi IP: Not available"
    }

    if ($adbStatus.ConnectedDevices) {
        Write-Host "  Wireless Connections:"
        foreach ($device in $adbStatus.ConnectedDevices) {
            Write-Host "    - $device"
        }
    } else {
        Write-Host "  No wireless connections found"
    }

    Write-Host ""
    exit 0
}

# Disable action
if ($Disable) {
    Write-Host "[$Yellow]Disabling wireless ADB...$NC" -ForegroundColor $Yellow

    adb shell "setprop service.adb.tcp.port -1" 2>$null
    adb shell "stop adbd" 2>$null
    adb shell "start adbd" 2>$null

    Write-Host "[$Green]Wireless ADB disabled.$NC" -ForegroundColor $Green
    Write-Host "  Run 'adb connect <ip>:$Port' to re-enable when needed."
    Write-Host ""
    exit 0
}

# Enable action
if ($Enable) {
    Write-Host "[$Yellow]Enabling wireless ADB on port $Port...$NC" -ForegroundColor $Yellow

    # Get WiFi IP first
    $wifiIp = Get-DeviceWifiIp
    if (-not $wifiIp) {
        Write-Host "[$Red]Could not determine device WiFi IP.$NC" -ForegroundColor $Red
        Write-Host "  Make sure device is connected to WiFi."
        Write-Host ""
        exit 1
    }

    Write-Host "  Device WiFi IP: $wifiIp"

    # Enable TCP/IP mode
    $result = adb tcpip $Port 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[$Red]Failed to enable TCP/IP mode.$NC" -ForegroundColor $Red
        Write-Host "  $result"
        Write-Host ""
        exit 1
    }

    Write-Host "[$Green]TCP/IP mode enabled on port $Port.$NC" -ForegroundColor $Green

    # Auto-connect if requested
    if ($AutoConnect -or $PSBoundParameters.ContainsKey('Enable')) {
        Write-Host "  Connecting to $wifiIp`:$Port..."
        $connectResult = adb connect "$wifiIp`:$Port" 2>&1
        if ($connectResult -match "connected") {
            Write-Host "[$Green]Successfully connected to $wifiIp`:$Port$NC" -ForegroundColor $Green
        } else {
            Write-Host "[$Red]Connection failed: $connectResult$NC" -ForegroundColor $Red
            Write-Host "  Manual connect: adb connect $wifiIp`:$Port"
        }
    }

    Write-Host ""

    # Show current status
    $adbStatus = Get-WirelessAdbStatus
    if ($adbStatus.TcpPort) {
        Write-Host "[$Green]Wireless ADB Status:$NC" -ForegroundColor $Green
        Write-Host "  TCP Port: $($adbStatus.TcpPort)"
        Write-Host "  WiFi IP: $($adbStatus.WifiIp)"
        if ($AutoConnect) {
            Write-Host "  Connected devices:"
            foreach ($device in $adbStatus.ConnectedDevices) {
                Write-Host "    - $device"
            }
        }
    }

    Write-Host ""
    exit 0
}

# Default: show help
if (-not $Enable -and -not $Disable -and -not $Status) {
    Write-Host "Usage: .\adb_wireless_setup.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Enable      Enable wireless ADB (auto-connects if auto-connect enabled)"
    Write-Host "  -Disable     Disable wireless ADB, return to USB-only mode"
    Write-Host "  -Status      Show current wireless ADB status"
    Write-Host "  -Port        Port for wireless ADB (default: 5555)"
    Write-Host "  -AutoConnect Automatically connect after enabling"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\adb_wireless_setup.ps1 -Enable              # Enable wireless ADB"
    Write-Host "  .\adb_wireless_setup.ps1 -Disable             # Disable wireless ADB"
    Write-Host "  .\adb_wireless_setup.ps1 -Status              # Show status"
    Write-Host "  .\adb_wireless_setup.ps1 -Enable -AutoConnect # Enable and connect"
    Write-Host ""
    exit 0
}