# Instala el vigilante y lo deja arrancando solo al iniciar sesion en Windows.
# Uso: doble clic en windows\instalar.bat (o ejecutar este script en PowerShell).

$ErrorActionPreference = "Stop"
$NombreTarea = "VigilanteHormiguero"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

Write-Host "== Carpeta del proyecto: $Raiz"

# 1. Localizar Python 3.10 o superior
$Python = $null
foreach ($candidato in @(@("py", "-3"), @("python"))) {
    if (Get-Command $candidato[0] -ErrorAction SilentlyContinue) {
        $exe = $candidato[0]
        $argsPy = @($candidato | Select-Object -Skip 1)
        & $exe @argsPy -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $Python = $candidato; break }
    }
}
if (-not $Python) {
    throw "No encuentro Python 3.10+. Instalalo desde https://www.python.org/downloads/ (marca 'Add python.exe to PATH') y vuelve a ejecutar."
}

# 2. Entorno virtual y dependencias
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "== Creando entorno virtual..."
    $exe = $Python[0]; $argsPy = @($Python | Select-Object -Skip 1)
    & $exe @argsPy -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual." }
}
$Py = Join-Path $Raiz ".venv\Scripts\python.exe"
$PyW = Join-Path $Raiz ".venv\Scripts\pythonw.exe"

Write-Host "== Instalando dependencias..."
& $Py -m pip install --disable-pip-version-check -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Fallo instalando dependencias." }

# 3. Configuracion de Telegram
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "== Rellena TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en el Bloc de notas, guarda y cierralo."
    Start-Process notepad.exe ".env" -Wait
}

# 4. Pruebas y mensaje de prueba
Write-Host "== Ejecutando pruebas..."
& $Py -m unittest discover -s pruebas -p "test_*.py"
if ($LASTEXITCODE -ne 0) { throw "Las pruebas han fallado." }

Write-Host "== Enviando mensaje de prueba a Telegram..."
& $Py src\vigilante.py --probar-telegram
if ($LASTEXITCODE -ne 0) { throw "No llego el mensaje de Telegram. Revisa el fichero .env." }

Write-Host "== Comprobando la web una vez (sin avisos)..."
& $Py src\vigilante.py --una-vez

# 5. Tarea programada: arranca al iniciar sesion y se reinicia si se cae
Write-Host "== Registrando la tarea programada '$NombreTarea'..."
$usuario = "$env:USERDOMAIN\$env:USERNAME"
$accion = New-ScheduledTaskAction -Execute $PyW -Argument "`"$Raiz\src\vigilante.py`"" -WorkingDirectory $Raiz
$disparador = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$ajustes = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Stop-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $NombreTarea -Action $accion -Trigger $disparador `
    -Principal $principal -Settings $ajustes -Force `
    -Description "Vigila las entradas de publico de El Hormiguero y avisa por Telegram" | Out-Null
Start-ScheduledTask -TaskName $NombreTarea

Write-Host ""
Write-Host "Listo. El vigilante esta funcionando en segundo plano." -ForegroundColor Green
Write-Host "Deberias recibir un Telegram de 'Vigilante Hormiguero arrancado'."
Write-Host "Registro: $Raiz\logs\vigilante.log"
Write-Host "IMPORTANTE: configura Windows para que el PC no entre en suspension."
