& (Join-Path $PSScriptRoot "detener.ps1")
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Vigilante El Hormiguero.lnk"
if (Test-Path $lnk) { Remove-Item $lnk; Write-Host "Quitado del arranque automatico." }
Write-Host "Hecho. (La carpeta del proyecto no se borra.)"
