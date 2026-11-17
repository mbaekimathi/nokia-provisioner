# Start Nokia Hotspot Provisioner (Django API + React UI) in this terminal
$root = $PSScriptRoot

$backend = Start-Process -NoNewWindow -PassThru -FilePath "python" `
    -ArgumentList "manage.py runserver 127.0.0.1:8000" `
    -WorkingDirectory "$root\backend"

Write-Host ""
Write-Host "Backend: http://127.0.0.1:8000"
Write-Host "Frontend: http://localhost:5173"
Write-Host ""

Start-Sleep -Seconds 3
Set-Location "$root\frontend"

try {
    npm run dev
} finally {
    taskkill /T /F /PID $backend.Id 2>$null | Out-Null
}
