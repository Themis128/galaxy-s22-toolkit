# =============================================================================
# Optimized ADB Workflow for Samsung Galaxy S22+ (SM_S906B)
# Based on Microsoft Learn documentation and Android development best practices
# =============================================================================

# Configuration
$DeviceSerial = "RFCTA0AEKZP"
$AdbPath = "C:\Users\tbaltzakis\Android\Sdk\platform-tools\adb.exe"
$DeviceIP = ""  # Will be auto-detected

# =============================================================================
# CORE FUNCTIONS
# =============================================================================

function Get-DeviceIP {
    """Get device Wi-Fi IP address"""
    $output = & $AdbPath -s $DeviceSerial shell "ip -f inet addr show wlan0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}'"
    return $output.Trim()
}

function Adb-Connect {
    param([string]$IP = "", [int]$Port = 5555)
    if (-not $IP) { $IP = Get-DeviceIP }
    & $AdbPath tcpip $Port
    Start-Sleep 2
    & $AdbPath connect "$IP:$Port"
    $global:DeviceIP = $IP
    Write-Host "Connected to $IP:$Port" -ForegroundColor Green
}

function Adb-Disconnect {
    param([string]$IP = "")
    if (-not $IP) { $IP = $global:DeviceIP }
    & $AdbPath disconnect "$IP:5555"
    Write-Host "Disconnected from $IP" -ForegroundColor Yellow
}

function Adb-Devices {
    & $AdbPath devices -l
}

# =============================================================================
# APP MANAGEMENT
# =============================================================================

function Adb-Install {
    param([string]$ApkPath, [switch]$Replace, [switch]$Test, [switch]$GrantPermissions)
    $args = @()
    if ($Replace) { $args += "-r" }
    if ($Test) { $args += "-t" }
    if ($GrantPermissions) { $args += "-g" }
    $args += $ApkPath
    & $AdbPath -s $DeviceSerial install @args
}

function Adb-Uninstall {
    param([string]$PackageName, [switch]$KeepData)
    $args = @()
    if ($KeepData) { $args += "-k" }
    $args += $PackageName
    & $AdbPath -s $DeviceSerial uninstall @args
}

function Adb-ListPackages {
    param([string]$Filter = "", [switch]$System, [switch]$ThirdParty, [switch]$Enabled, [switch]$Disabled)
    $args = @("shell", "pm", "list", "packages")
    if ($System) { $args += "-s" }
    if ($ThirdParty) { $args += "-3" }
    if ($Enabled) { $args += "-e" }
    if ($Disabled) { $args += "-d" }
    $output = & $AdbPath -s $DeviceSerial @args
    if ($Filter) { $output | Select-String $Filter } else { $output }
}

function Adb-ClearData {
    param([string]$PackageName)
    & $AdbPath -s $DeviceSerial shell pm clear $PackageName
}

function Adb-GrantPermissions {
    param([string]$PackageName)
    & $AdbPath -s $DeviceSerial shell pm grant $PackageName android.permission.READ_EXTERNAL_STORAGE
    & $AdbPath -s $DeviceSerial shell pm grant $PackageName android.permission.WRITE_EXTERNAL_STORAGE
    & $AdbPath -s $DeviceSerial shell pm grant $PackageName android.permission.CAMERA
    & $AdbPath -s $DeviceSerial shell pm grant $PackageName android.permission.RECORD_AUDIO
    & $AdbPath -s $DeviceSerial shell pm grant $PackageName android.permission.ACCESS_FINE_LOCATION
    & $AdbPath -s $DeviceSerial shell pm grant $PackageName android.permission.ACCESS_COARSE_LOCATION
}

# =============================================================================
# LOGCAT - OPTIMIZED FOR DEVELOPMENT
# =============================================================================

function Adb-Logcat {
    param(
        [string]$Filter = "",
        [string]$Tag = "",
        [string]$Level = "V",
        [switch]$Color,
        [switch]$Time,
        [switch]$Thread,
        [switch]$PID,
        [int]$Lines = 0
    )
    $args = @("-s", $DeviceSerial, "logcat")
    if ($Color) { $args += "-v", "color" }
    elseif ($Time) { $args += "-v", "time" }
    elseif ($Thread) { $args += "-v", "threadtime" }
    else { $args += "-v", "brief" }

    if ($PID) {
        $pid = & $AdbPath -s $DeviceSerial shell "pidof $Filter"
        if ($pid) { $args += "--pid=$pid" }
    }
    elseif ($Tag) {
        $args += "$Tag:$Level"
    }
    elseif ($Filter) {
        $args += "$Filter:$Level"
    }
    else {
        $args += "*:$Level"
    }

    if ($Lines -gt 0) {
        $args += "-t", $Lines.ToString()
    }

    & $AdbPath @args
}

function Adb-Logcat-App {
    param([string]$PackageName, [string]$Level = "V", [int]$Lines = 0)
    $pid = & $AdbPath -s $DeviceSerial shell "pidof $PackageName"
    if ($pid) {
        Adb-Logcat -Filter $PackageName -Level $Level -Lines $Lines -PID
    }
}

function Adb-Logcat-Errors {
    param([int]$Lines = 100)
    Adb-Logcat -Level "E" -Lines $Lines
}

function Adb-Logcat-Warnings {
    param([int]$Lines = 100)
    Adb-Logcat -Level "W" -Lines $Lines
}

function Adb-Logcat-Crash {
    param([int]$Lines = 50)
    Adb-Logcat -Tag "AndroidRuntime" -Level "E" -Lines $Lines
}

function Adb-Logcat-System {
    param([string]$Tag = "", [int]$Lines = 100)
    if ($Tag) {
        Adb-Logcat -Tag $Tag -Level "V" -Lines $Lines
    } else {
        Adb-Logcat -Filter "SystemServer" -Level "V" -Lines $Lines
    }
}

# =============================================================================
# FILE TRANSFER
# =============================================================================

function Adb-Push {
    param([string]$LocalPath, [string]$RemotePath)
    & $AdbPath -s $DeviceSerial push $LocalPath $RemotePath
}

function Adb-Pull {
    param([string]$RemotePath, [string]$LocalPath = ".")
    & $AdbPath -s $DeviceSerial pull $RemotePath $LocalPath
}

function Adb-Sync {
    param([string]$LocalDir, [string]$RemoteDir = "/sdcard/")
    & $AdbPath -s $DeviceSerial sync $LocalDir $RemoteDir
}

# =============================================================================
# SCREENSHOTS & SCREEN RECORDING
# =============================================================================

function Adb-Screenshot {
    param([string]$RemotePath = "/sdcard/screenshot_$(Get-Date -Format 'yyyyMMdd_HHmmss').png", [string]$LocalPath = ".")
    & $AdbPath -s $DeviceSerial shell screencap -p $RemotePath
    & $AdbPath -s $DeviceSerial pull $RemotePath $LocalPath
    & $AdbPath -s $DeviceSerial shell rm $RemotePath
    Write-Host "Screenshot saved to $LocalPath" -ForegroundColor Green
}

function Adb-ScreenRecord {
    param([string]$RemotePath = "/sdcard/record_$(Get-Date -Format 'yyyyMMdd_HHmmss').mp4", [int]$TimeLimit = 180, [int]$BitRate = 4000000, [string]$LocalPath = ".")
    Write-Host "Recording for $TimeLimit seconds... Press Ctrl+C to stop early" -ForegroundColor Yellow
    $job = Start-Job -ScriptBlock {
        param($AdbPath, $DeviceSerial, $RemotePath, $TimeLimit, $BitRate)
        & $AdbPath -s $DeviceSerial shell screenrecord --time-limit $TimeLimit --bit-rate $BitRate $RemotePath
    } -ArgumentList $AdbPath, $DeviceSerial, $RemotePath, $TimeLimit, $BitRate

    try {
        $job | Wait-Job -Timeout 1
    }
    catch {
        # User pressed Ctrl+C
    }
    finally {
        $job | Stop-Job
        Start-Sleep 1
        & $AdbPath -s $DeviceSerial pull $RemotePath $LocalPath
        & $AdbPath -s $DeviceSerial shell rm $RemotePath
        Write-Host "Recording saved to $LocalPath" -ForegroundColor Green
    }
}

# =============================================================================
# SHELL COMMANDS & DEBUGGING
# =============================================================================

function Adb-Shell {
    param([string]$Command = "")
    if ($Command) {
        & $AdbPath -s $DeviceSerial shell $Command
    } else {
        & $AdbPath -s $DeviceSerial shell
    }
}

function Adb-Root {
    & $AdbPath -s $DeviceSerial root
}

function Adb-Remount {
    & $AdbPath -s $DeviceSerial remount
}

function Adb-GetProp {
    param([string]$Prop = "")
    if ($Prop) {
        & $AdbPath -s $DeviceSerial shell getprop $Prop
    } else {
        & $AdbPath -s $DeviceSerial shell getprop
    }
}

function Adb-SetProp {
    param([string]$Prop, [string]$Value)
    & $AdbPath -s $DeviceSerial shell setprop $Prop $Value
}

function Adb-Dumpsys {
    param([string]$Service = "", [string]$Args = "")
    if ($Service) {
        & $AdbPath -s $DeviceSerial shell dumpsys $Service $Args
    } else {
        & $AdbPath -s $DeviceSerial shell dumpsys | Select-String "DUMP OF SERVICE"
    }
}

function Adb-BatteryStats {
    Adb-Dumpsys -Service "batterystats"
}

function Adb-MemInfo {
    param([string]$PackageName = "")
    if ($PackageName) {
        Adb-Dumpsys -Service "meminfo" -Args $PackageName
    } else {
        Adb-Dumpsys -Service "meminfo"
    }
}

function Adb-CpuInfo {
    Adb-Dumpsys -Service "cpuinfo"
}

function Adb-ActivityManager {
    param([string]$Command = "")
    Adb-Dumpsys -Service "activity" -Args $Command
}

function Adb-PackageManager {
    param([string]$Command = "")
    Adb-Dumpsys -Service "package" -Args $Command
}

# =============================================================================
# INPUT & UI AUTOMATION
# =============================================================================

function Adb-Tap {
    param([int]$X, [int]$Y)
    & $AdbPath -s $DeviceSerial shell input tap $X $Y
}

function Adb-Swipe {
    param([int]$X1, [int]$Y1, [int]$X2, [int]$Y2, [int]$Duration = 300)
    & $AdbPath -s $DeviceSerial shell input swipe $X1 $Y1 $X2 $Y2 $Duration
}

function Adb-Text {
    param([string]$Text)
    & $AdbPath -s $DeviceSerial shell input text "$Text"
}

function Adb-KeyEvent {
    param([string]$Key)
    & $AdbPath -s $DeviceSerial shell input keyevent $Key
}

# Common keys: KEYCODE_HOME(3), KEYCODE_BACK(4), KEYCODE_MENU(82), KEYCODE_APP_SWITCH(187), KEYCODE_POWER(26)
# ENTER=66, SEARCH=84, VOLUME_UP=24, VOLUME_DOWN=25

# =============================================================================
# NETWORK & PORT FORWARDING
# =============================================================================

function Adb-Forward {
    param([string]$LocalPort, [string]$RemotePort)
    & $AdbPath -s $DeviceSerial forward tcp:$LocalPort tcp:$RemotePort
}

function Adb-Forward-Remove {
    param([string]$LocalPort)
    & $AdbPath -s $DeviceSerial forward --remove tcp:$LocalPort
}

function Adb-Forward-List {
    & $AdbPath -s $DeviceSerial forward --list
}

function Adb-Reverse {
    param([string]$RemotePort, [string]$LocalPort)
    & $AdbPath -s $DeviceSerial reverse tcp:$RemotePort tcp:$LocalPort
}

# =============================================================================
# DEBUGGING & PROFILING
# =============================================================================

function Adb-Bugreport {
    param([string]$OutputPath = ".")
    $filename = "bugreport_$(Get-Date -Format 'yyyyMMdd_HHmmss').zip"
    & $AdbPath -s $DeviceSerial bugreport $OutputPath\$filename
    Write-Host "Bugreport saved to $OutputPath\$filename" -ForegroundColor Green
}

function Adb-Profile {
    param([string]$PackageName, [string]$OutputPath = ".")
    $filename = "profile_$(Get-Date -Format 'yyyyMMdd_HHmmss').trace"
    & $AdbPath -s $DeviceSerial shell am profile start $PackageName $OutputPath\$filename
    Write-Host "Profiling started. Press Enter to stop..." -ForegroundColor Yellow
    Read-Host
    & $AdbPath -s $DeviceSerial shell am profile stop $PackageName
    & $AdbPath -s $DeviceSerial pull $OutputPath\$filename $OutputPath
    Write-Host "Profile saved to $OutputPath\$filename" -ForegroundColor Green
}

function Adb-Systrace {
    param([int]$Duration = 10, [string]$OutputPath = ".")
    $filename = "systrace_$(Get-Date -Format 'yyyyMMdd_HHmmss').html"
    & $AdbPath -s $DeviceSerial shell atrace --async_start -b 64000 -t $Duration sched freq idle am wm gfx view binder_driver hal dalvik camera input res memory
    Start-Sleep $Duration
    & $AdbPath -s $DeviceSerial shell atrace --async_stop -b 64000 -t $Duration sched freq idle am wm gfx view binder_driver hal dalvik camera input res memory > $OutputPath\$filename
    Write-Host "Systrace saved to $OutputPath\$filename" -ForegroundColor Green
}

# =============================================================================
# APP DEBUGGING SHORTCUTS
# =============================================================================

function Adb-StartApp {
    param([string]$PackageName, [string]$Activity = "")
    if ($Activity) {
        & $AdbPath -s $DeviceSerial shell am start -n "$PackageName/$Activity"
    } else {
        & $AdbPath -s $DeviceSerial shell monkey -p $PackageName -c android.intent.category.LAUNCHER 1
    }
}

function Adb-StopApp {
    param([string]$PackageName)
    & $AdbPath -s $DeviceSerial shell am force-stop $PackageName
}

function Adb-RestartApp {
    param([string]$PackageName, [string]$Activity = "")
    Adb-StopApp $PackageName
    Start-Sleep 1
    Adb-StartApp $PackageName $Activity
}

function Adb-ClearAndStart {
    param([string]$PackageName, [string]$Activity = "")
    Adb-ClearData $PackageName
    Adb-StartApp $PackageName $Activity
}

function Adb-GetAppInfo {
    param([string]$PackageName)
    & $AdbPath -s $DeviceSerial shell dumpsys package $PackageName
}

# =============================================================================
# DATABASE & SHARED PREFS
# =============================================================================

function Adb-DbShell {
    param([string]$PackageName, [string]$DbName)
    $path = "/data/data/$PackageName/databases/$DbName"
    & $AdbPath -s $DeviceSerial shell "run-as $PackageName sqlite3 $path"
}

function Adb-PrefsView {
    param([string]$PackageName, [string]$PrefsFile = "")
    if ($PrefsFile) {
        $path = "/data/data/$PackageName/shared_prefs/$PrefsFile.xml"
        & $AdbPath -s $DeviceSerial shell "run-as $PackageName cat $path"
    } else {
        & $AdbPath -s $DeviceSerial shell "run-as $PackageName ls /data/data/$PackageName/shared_prefs/"
    }
}

# =============================================================================
# QUICK SETUP ALIASES
# =============================================================================

Set-Alias -Name adbi -Value Adb-Install
Set-Alias -Name adbu -Value Adb-Uninstall
Set-Alias -Name adbl -Value Adb-ListPackages
Set-Alias -Name adblc -Value Adb-Logcat
Set-Alias -Name adblce -Value Adb-Logcat-Errors
Set-Alias -Name adblcw -Value Adb-Logcat-Warnings
Set-Alias -Name adblcc -Value Adb-Logcat-Crash
Set-Alias -Name adbs -Value Adb-Screenshot
Set-Alias -Name adbsr -Value Adb-ScreenRecord
Set-Alias -Name adbsh -Value Adb-Shell
Set-Alias -Name adbpush -Value Adb-Push
Set-Alias -Name adbpull -Value Adb-Pull
Set-Alias -Name adbdev -Value Adb-Devices
Set-Alias -Name adbconn -Value Adb-Connect
Set-Alias -Name adbdis -Value Adb-Disconnect

# =============================================================================
# WIRELESS ADB QUICK SETUP
# =============================================================================

function Setup-WirelessAdb {
    Write-Host "=== Wireless ADB Setup for Samsung Galaxy S22+ ===" -ForegroundColor Cyan
    Write-Host "Device: $DeviceSerial (SM_S906B)" -ForegroundColor Gray

    # Step 1: Enable TCP/IP mode
    Write-Host "`n1. Enabling TCP/IP mode on port 5555..." -ForegroundColor Yellow
    & $AdbPath -s $DeviceSerial tcpip 5555
    Start-Sleep 2

    # Step 2: Get IP
    Write-Host "2. Getting device IP address..." -ForegroundColor Yellow
    $ip = Get-DeviceIP
    if (-not $ip) {
        Write-Host "ERROR: Could not detect IP. Make sure Wi-Fi is on and connected." -ForegroundColor Red
        return
    }
    Write-Host "   Device IP: $ip" -ForegroundColor Green

    # Step 3: Connect wirelessly
    Write-Host "3. Connecting wirelessly..." -ForegroundColor Yellow
    $result = & $AdbPath connect "$ip:5555"

    if ($result -like "*connected*") {
        Write-Host "`n✅ Wireless ADB connected successfully!" -ForegroundColor Green
        Write-Host "   You can now disconnect the USB cable." -ForegroundColor Cyan
        $global:DeviceIP = $ip
    } else {
        Write-Host "`n❌ Wireless connection failed:" -ForegroundColor Red
        Write-Host "   $result" -ForegroundColor Red
        Write-Host "`nTroubleshooting:" -ForegroundColor Yellow
        Write-Host "  - Ensure phone and PC are on SAME Wi-Fi network" -ForegroundColor Gray
        Write-Host "  - Try: adb kill-server && adb start-server" -ForegroundColor Gray
        Write-Host "  - Toggle USB debugging off/on on phone" -ForegroundColor Gray
        Write-Host "  - Check firewall allows port 5555" -ForegroundColor Gray
    }
}

# =============================================================================
# DEVELOPMENT WORKFLOW PRESETS
# =============================================================================

function Workflow-AppDebug {
    param([string]$PackageName)
    Write-Host "=== App Debug Workflow for $PackageName ===" -ForegroundColor Cyan
    Adb-Logcat-App $PackageName -Level "V" -Lines 50
}

function Workflow-AppInstallDebug {
    param([string]$ApkPath, [string]$PackageName)
    Write-Host "=== Install & Debug Workflow ===" -ForegroundColor Cyan
    Adb-Install $ApkPath -Replace -GrantPermissions
    Adb-Logcat-App $PackageName -Level "V"
}

function Workflow-PerfCheck {
    param([string]$PackageName)
    Write-Host "=== Performance Check ===" -ForegroundColor Cyan
    Adb-MemInfo $PackageName
    Write-Host "`n--- CPU Info ---" -ForegroundColor Yellow
    Adb-CpuInfo
    Write-Host "`n--- Battery Stats ---" -ForegroundColor Yellow
    Adb-BatteryStats
}

# =============================================================================
# EXPORT FUNCTIONS FOR POWERSHELL PROFILE
# =============================================================================

Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host "ADB Workflow loaded for Samsung Galaxy S22+" -ForegroundColor Cyan
Write-Host "Device: $DeviceSerial" -ForegroundColor Gray
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "`nQuick Commands:" -ForegroundColor Yellow
Write-Host "  Setup-WirelessAdb     - One-command wireless setup" -ForegroundColor Gray
Write-Host "  Adb-Connect           - Connect to wireless device" -ForegroundColor Gray
Write-Host "  Adb-Devices           - List connected devices" -ForegroundColor Gray
Write-Host "  Adb-Logcat-App <pkg>  - Filtered logcat for app" -ForegroundColor Gray
Write-Host "  Adb-Screenshot        - Take & pull screenshot" -ForegroundColor Gray
Write-Host "  Adb-ScreenRecord      - Record screen (180s default)" -ForegroundColor Gray
Write-Host "  Adb-Install <apk>     - Install with permissions" -ForegroundColor Gray
Write-Host "  Adb-ListPackages -3   - List user-installed apps" -ForegroundColor Gray
Write-Host "  Workflow-AppDebug <pkg> - Full app debugging session" -ForegroundColor Gray
Write-Host "`nAliases: adbi, adbu, adbl, adblc, adblce, adblcw, adblcc, adbs, adbsr, adbsh, adbpush, adbpull, adbdev, adbconn, adbdis" -ForegroundColor Gray