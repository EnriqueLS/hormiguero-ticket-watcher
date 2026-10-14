# Detiene y elimina la tarea programada del vigilante.
$NombreTarea = "VigilanteHormiguero"
Stop-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Tarea '$NombreTarea' eliminada. Los ficheros del proyecto no se tocan."
