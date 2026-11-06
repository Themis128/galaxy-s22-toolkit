$tasks = Get-ScheduledTask -TaskPath '\Phone Toolkit\'
foreach ($t in $tasks) {
    foreach ($a in $t.Actions) {
        Write-Host "Task: $($t.TaskName)"
        Write-Host "  Path: $($a.Path)"
        Write-Host "  Args: $($a.Arguments)"
        Write-Host "  WorkDir: $($a.WorkingDirectory)"
    }
}