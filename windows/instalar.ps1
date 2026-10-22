# Instalador del vigilante de El Hormiguero para Windows.
# - Crea el entorno de Python e instala dependencias
# - Pide el token y el chat id de Telegram (solo la primera vez)
# - Envia un mensaje de prueba
# - NO arranca solo con Windows: se lanza a mano con INICIAR VIGILANTE.bat
param([switch]$SinPausa)
$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz
Write-Host ""
Write-Host "=== Vigilante El Hormiguero - instalacion ===" -ForegroundColor Cyan
Write-Host "Carpeta: $Raiz"

# 1. Python
function Buscar-Python {
    foreach ($c in @("py", "python", "python3")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike "*WindowsApps*") {
            if ($c -eq "py") { return @("py", "-3") }
            return @($cmd.Source)
        }
    }
    return $null
}
$py = Buscar-Python
if (-not $py) {
    Write-Host "No encuentro Python. Intento instalarlo con winget..." -ForegroundColor Yellow
    try {
        winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    } catch {
        Write-Host "No se pudo instalar automaticamente. Instala Python desde https://www.python.org/downloads/ (marca 'Add python.exe to PATH') y vuelve a ejecutar instalar.bat" -ForegroundColor Red
        Read-Host "Pulsa Enter para salir"; exit 1
    }
    Write-Host "Python instalado. CIERRA esta ventana y vuelve a ejecutar INICIAR VIGILANTE.bat" -ForegroundColor Green
    Read-Host "Pulsa Enter para salir"; exit 1
}

# 2. Entorno virtual + dependencias
$venvPy = Join-Path $Raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creando entorno de Python..."
    $exe = $py[0]; $resto = @(); if ($py.Count -gt 1) { $resto = $py[1..($py.Count-1)] }
    & $exe @resto -m venv .venv
}
Write-Host "Instalando dependencias..."
& $venvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
& $venvPy -m pip install -r requirements.txt --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { Write-Host "Fallo instalando dependencias" -ForegroundColor Red; Read-Host "Enter"; exit 1 }

# 3. Configuracion de Telegram
$envFile = Join-Path $Raiz ".env"
if (-not (Test-Path $envFile)) {
    Write-Host ""
    Write-Host "Necesito los datos de tu bot de Telegram (los mismos que pusiste en los secretos de GitHub)." -ForegroundColor Cyan
    Write-Host " - Token: te lo da @BotFather (algo como 123456:ABC-...)"
    Write-Host " - Chat id: tu id numerico (puedes verlo con @userinfobot)"
    $token = Read-Host "TELEGRAM_BOT_TOKEN"
    $chat = Read-Host "TELEGRAM_CHAT_ID"
    $plantilla = Get-Content (Join-Path $Raiz "configuracion_ejemplo.txt") -Raw
    $plantilla = $plantilla -replace "pon_aqui_el_token_del_bot", $token.Trim()
    $plantilla = $plantilla -replace "pon_aqui_tu_chat_id", $chat.Trim()
    [IO.File]::WriteAllText($envFile, $plantilla, (New-Object Text.UTF8Encoding $false))
    Write-Host "Guardado en .env (puedes editarlo con el Bloc de notas)."
}

# 4. Prueba de Telegram
Write-Host ""
Write-Host "Enviando mensaje de prueba a Telegram..."
& $venvPy (Join-Path $Raiz "src\telegram.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host "La prueba de Telegram ha fallado. Revisa el token y el chat id en .env y vuelve a ejecutar instalar.bat" -ForegroundColor Red
    Write-Host "(Recuerda escribirle /start a tu bot desde Telegram al menos una vez.)"
    Read-Host "Pulsa Enter para salir"; exit 1
}

# 5. Prueba de lectura de la web
Write-Host ""
Write-Host "Comprobando la web de entradas una vez..."
& $venvPy (Join-Path $Raiz "src\vigilante.py") --una-vez

# 6. Sin arranque automatico: se lanza a mano con "INICIAR VIGILANTE.bat"
$lnk = Join-Path ([Environment]::GetFolderPath("Startup")) "Vigilante El Hormiguero.lnk"
if (Test-Path $lnk) { Remove-Item $lnk -ErrorAction SilentlyContinue }
Write-Host ""
Write-Host "INSTALACION TERMINADA." -ForegroundColor Green
Write-Host "Para lanzarlo: doble clic en 'INICIAR VIGILANTE.bat' (en la carpeta del proyecto)."
Write-Host "Para pararlo: cierra esa ventana."
if (-not $SinPausa) { Read-Host "Pulsa Enter para cerrar" }
