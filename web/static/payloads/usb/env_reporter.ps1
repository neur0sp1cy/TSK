# TSK built-in | Env Reporter (Windows)
# Writes whoami and environment snapshot next to this script on the USB stick.
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$out  = Join-Path $here "tsk_env_report.txt"
$lines = @(
    "TSK Env Reporter",
    "================",
    "whoami: $(whoami.exe 2>&1)",
    "date:   $(Get-Date -Format o)",
    "",
    "--- environment ---"
)
$lines += Get-ChildItem Env: | ForEach-Object { "$($_.Name)=$($_.Value)" }
$lines | Out-File -FilePath $out -Encoding utf8
