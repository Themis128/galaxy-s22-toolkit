<# 
.SYNOPSIS
    Install Galaxy S22+ Diagnostics as a Windows Scheduled Task

.DESCRIPTION
    This script installs the diagnostics runner as a daily scheduled task
    using the task_scheduler.xml configuration.

.EXAMPLE
    .\install_task.ps1
#>

param(
    [string]$ProjectPath = "C:\dev\galaxy-s22-toolkit",
    [string]$TaskName = "Galaxy S22+ Diagnostics",
    [string]$XmlPath = "diagnostics\task_scheduler.xml"
)

$fullXmlPath = Join-Path $ProjectPath $XmlPath

if (-not (Test-Path $fullXmlPath)) {
    Write-Error "Task XML not found: $fullXmlPath"
    exit 1
}

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Task '$TaskName' already exists. Updating..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Register the task
try {
    Register-ScheduledTask -Xml (Get-Content $fullXmlPath -Raw) -TaskName $TaskName -Force
    Write-Host "Successfully installed task: $TaskName"
    
    # Show task details
    $task = Get-ScheduledTask -TaskName $TaskName
    Write-Host "Next run: $($task.Triggers[0].StartBoundary)"
    Write-Host "Task path: $($task.TaskPath)"
}
catch {
    Write-Error "Failed to install task: $_"
    exit 1
}