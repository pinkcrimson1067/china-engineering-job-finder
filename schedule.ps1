param([string]$At = '09:00')
$ErrorActionPreference = 'Stop'
if ($At -notmatch '^([01]\d|2[0-3]):[0-5]\d$') { throw '时间格式应为 HH:mm，例如 09:00' }
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python -ErrorAction Stop).Source
$action = New-ScheduledTaskAction -Execute $python -Argument ('"' + (Join-Path $project 'job_finder.py') + '" --config "' + (Join-Path $project 'config.json') + '"') -WorkingDirectory $project
$trigger = New-ScheduledTaskTrigger -Daily -At $At
Register-ScheduledTask -TaskName 'PersonalJobFinder' -Action $action -Trigger $trigger -Description '每日查询公开职位 API 并生成本地报告' -Force | Out-Null
Write-Host "已创建任务 PersonalJobFinder，每天 $At 运行。"

