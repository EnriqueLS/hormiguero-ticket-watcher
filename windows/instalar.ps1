# Instalador del vigilante de El Hormiguero para Windows.
# - Crea el entorno de Python e instala dependencias
# - Pide el token y el chat id de Telegram (solo la primera vez)
# - Envia un mensaje de prueba
# - Hace que arranque solo al iniciar sesion en Windows y lo lanza ya
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
    Write-Host "Python instalado. CIERRA esta ventana y vuelve a ejecutar instalar.bat" -ForegroundColor Green
    Read-Host "Pulsa Enter para salir"; exit 0
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
    $plantilla = Get-Content (Join-Path $Raiz ".env.ejemplo") -Raw
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

# 6. Arranque automatico al iniciar sesion (acceso directo en Inicio, sin permisos de admin)
$pyw = Join-Path $Raiz ".venv\Scripts\pythonw.exe"
$script = Join-Path $Raiz "src\vigilante.py"
$inicio = [Environment]::GetFolderPath("Startup")
$lnk = Join-Path $inicio "Vigilante El Hormiguero.lnk"
$shell = New-Object -ComObject WScript.Shell
$acceso = $shell.CreateShortcut($lnk)
$acceso.TargetPath = $pyw
$acceso.Arguments = "`"$script`" --continuo"
$acceso.WorkingDirectory = $Raiz
$acceso.WindowStyle = 7
$acceso.Description = "Vigilante de entradas de El Hormiguero"
$acceso.Save()
Write-Host "Arranque automatico configurado: $lnk"

# 7. Parar si ya habia uno y lanzarlo ahora
& (Join-Path $PSScriptRoot "detener.ps1") -Silencioso
Start-Process -FilePath $pyw -ArgumentList "`"$script`" --continuo" -WorkingDirectory $Raiz -WindowStyle Hidden
Start-Sleep -Seconds 3
Write-Host ""
Write-Host "LISTO. El vigilante esta funcionando en segundo plano (sin ventana)." -ForegroundColor Green
Write-Host "Te llegara un Telegram de 'Vigilante arrancado'."
Write-Host " - Ver lo que hace:  windows\ver_log.bat"
Write-Host " - Pararlo:          windows\detener.bat"
Write-Host " - Quitarlo del todo: windows\desinstalar.bat"
Write-Host "IMPORTANTE: el PC debe estar encendido y sin suspender para que vigile."
Read-Host "Pulsa Enter para cerrar"
