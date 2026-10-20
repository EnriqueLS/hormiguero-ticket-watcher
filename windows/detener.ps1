param([switch]$Silencioso)
$procs = Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -like "*vigilante.py*--continuo*" }
foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
if (-not $Silencioso) {
    if ($procs) { Write-Host "Vigilante detenido." -ForegroundColor Yellow }
    else { Write-Host "No habia ningun vigilante funcionando." }
}
