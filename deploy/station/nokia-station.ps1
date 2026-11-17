# nokia-station.ps1 -- keep the relay tunnel alive from a Windows station PC.
# Requires only the built-in Windows OpenSSH client (ssh.exe).
#
#   .\nokia-station.ps1 -Key .\mombasa.ed25519 -Port 18443 -Router 192.168.1.254
#
# -Router accepts a comma-separated list; routers map onto consecutive ports
# (18443, 18444, ...). To run at logon, register it as a scheduled task:
#   schtasks /create /tn "NokiaStation" /sc onlogon /rl highest /f ^
#     /tr "powershell -WindowStyle Hidden -File C:\nokia\nokia-station.ps1 -Key C:\nokia\station.ed25519 -Port 18443"
param(
    [string]$Key    = ".\station.ed25519",
    [int]$Port      = 18443,
    [string]$Router = "192.168.1.254",
    [string]$Server = "178.162.241.99",
    [int]$SshPort   = 2222
)

$routers = $Router -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if ($routers.Count -gt 4) { Write-Error "max 4 routers per station"; exit 1 }

# OpenSSH ignores keys readable by other users - lock the ACL to this account.
icacls $Key /inheritance:r /grant:r "$($env:USERNAME):F" | Out-Null

Write-Host "nokia-station: $($routers.Count) router(s) on relay ports $Port..$($Port + $routers.Count - 1)"

while ($true) {
    $fwd = @()
    for ($i = 0; $i -lt $routers.Count; $i++) {
        $fwd += @("-R", "0.0.0.0:$($Port + $i):$($routers[$i]):443")
    }
    & ssh.exe -N -T -i $Key -p $SshPort `
        -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
        -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new `
        @fwd "tunnel@$Server"
    Write-Host "tunnel dropped -- reconnecting in 5s"
    Start-Sleep 5
}
