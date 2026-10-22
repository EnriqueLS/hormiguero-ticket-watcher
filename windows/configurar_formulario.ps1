# Asistente para configurar el rellenado automatico del formulario.
# Los datos se guardan SOLO en el archivo .env de esta carpeta, en tu PC.
param([switch]$SinPausa)
$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz
$envFile = Join-Path $Raiz ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "Primero lanza 'INICIAR VIGILANTE.bat' una vez para configurar Telegram." -ForegroundColor Yellow
    Read-Host "Pulsa Enter para salir"; exit 1
}

function Poner-Clave($clave, $valor) {
    $lineas = [System.Collections.Generic.List[string]](Get-Content $envFile -Encoding UTF8)
    $hecho = $false
    for ($i = 0; $i -lt $lineas.Count; $i++) {
        if ($lineas[$i] -match "^\s*$clave\s*=") { $lineas[$i] = "$clave=$valor"; $hecho = $true; break }
    }
    if (-not $hecho) { $lineas.Add("$clave=$valor") }
    [IO.File]::WriteAllLines($envFile, $lineas, (New-Object Text.UTF8Encoding $false))
}
function Actual($clave) {
    $l = Get-Content $envFile -Encoding UTF8 | Where-Object { $_ -match "^\s*$clave\s*=" } | Select-Object -First 1
    if ($l) { return ($l -split "=", 2)[1].Trim() } else { return "" }
}
function Preguntar($texto, $clave) {
    $act = Actual $clave
    $suf = ""; if ($act) { $suf = " [Enter = mantener: $act]" }
    $v = Read-Host "$texto$suf"
    if ($v.Trim()) { Poner-Clave $clave $v.Trim() }
}
function SiNo($texto, $clave) {
    $act = Actual $clave
    $r = Read-Host "$texto (s/n)"
    if ($r -match "^[sSyY1]") { Poner-Clave $clave "1" } elseif ($r -match "^[nN0]") { Poner-Clave $clave "0" }
}

Write-Host ""
Write-Host "=== Datos para rellenar el formulario ===" -ForegroundColor Cyan
Write-Host "(Se guardan solo en el archivo .env de tu PC.)"
Preguntar "Nombre" "DATOS_NOMBRE"
Preguntar "Apellidos" "DATOS_APELLIDOS"
Preguntar "DNI / NIE / Pasaporte" "DATOS_DNI"
Preguntar "Telefono" "DATOS_TELEFONO"
Preguntar "Email" "DATOS_EMAIL"
Preguntar "Numero de personas (maximo 8)" "DATOS_PERSONAS"

Write-Host ""
Write-Host "=== Opciones ===" -ForegroundColor Cyan
SiNo "Rellenar el formulario automaticamente en este PC cuando haya plazas?" "AUTO_RELLENAR"
SiNo "Ademas, PULSAR ENVIAR solo (si no hay captcha ni campos sin rellenar)?" "AUTO_ENVIAR"
SiNo "Marcar por mi la casilla de condiciones/privacidad? (sin esto no envia)" "ACEPTAR_CONDICIONES"

Write-Host ""
Write-Host "Instalando el componente de navegador (rapido)..."
$venvPy = Join-Path $Raiz ".venv\Scripts\python.exe"
& $venvPy -m pip install -r requirements.txt --quiet --disable-pip-version-check
Write-Host ""
Write-Host "Guardado. Cierra el vigilante si esta abierto y vuelve a lanzar 'INICIAR VIGILANTE.bat'." -ForegroundColor Green
if (-not $SinPausa) { Read-Host "Pulsa Enter para cerrar" }
