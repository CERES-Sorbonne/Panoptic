# Variables de configuration
$envDir = "$home\panoptic\panoptic_env"
$minPythonVersion = "3.10"
$targetPythonVersion = "3.12.7"
$pythonInstaller = "python-installer.exe"
$pythonDownloadUrl = "https://www.python.org/ftp/python/$targetPythonVersion/python-$targetPythonVersion-amd64.exe"

# Fonction d'installation de Python
function Install-Python {
    Write-Host "Installation de Python version $targetPythonVersion..."
    Invoke-WebRequest -Uri $pythonDownloadUrl -OutFile $pythonInstaller
    Start-Process -FilePath $pythonInstaller -ArgumentList "/passive", "InstallAllUsers=1", "PrependPath=1" -Wait
    Remove-Item $pythonInstaller
    $global:pythonExec = "python"
    $global:pipExec = "pip"
}

# Vérifie si Python >= 3.10 est installé
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Path
if (-not $pythonPath) {
    Write-Host "Python n'est pas installé. Téléchargement et installation..."
    Install-Python
} else {
    $pythonVersion = [System.Version]::Parse((python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null))
    if ($pythonVersion -ge [System.Version]::Parse($minPythonVersion)) {
        $global:pythonExec = "python"
        $global:pipExec = "pip"
    } else {
        Write-Host "Version de Python obsolète détectée. Mise à jour vers Python $targetPythonVersion..."
        Install-Python
    }
}

# Crée l'environnement virtuel si nécessaire
if (Test-Path $envDir) {
    Write-Host "L'environnement '$envDir' existe déjà. Activation..."
} else {
    Write-Host "Création de l'environnement virtuel '$envDir'..."
    & $pythonExec -m venv $envDir
    Write-Host "Installation de panoptic dans l'environnement virtuel..."
    & "$envDir\Scripts\Activate.ps1"
    & $pythonExec -m $pipExec install --upgrade pip
    & $pipExec install panoptic
}

# Active l'environnement virtuel
& "$envDir\Scripts\Activate.ps1"

# Vérifie s'il y a une mise à jour de panoptic disponible
$latestPanopticVersion = (& $pipExec install panoptic==nonexistent 2>&1 | Select-String -Pattern "from versions: ").ToString().Split()[-1]
$currentPanopticVersion = (& $pipExec show panoptic | Select-String -Pattern "Version").ToString().Split()[-1]

if ($latestPanopticVersion -gt $currentPanopticVersion -and $latestPanopticVersion -notmatch "rc") {
    Write-Host "Une nouvelle version de panoptic est disponible : $latestPanopticVersion (actuellement installée : $currentPanopticVersion)."
    $reply = Read-Host "Souhaitez-vous installer la dernière version stable ? (o/n)"
    if ($reply -match "^(o|O)$") {
        & $pipExec install -U panoptic
        Write-Host "Panoptic mis à jour vers la version $latestPanopticVersion."
    }
} else {
    Write-Host "Vous utilisez déjà la dernière version stable de panoptic."
}

# Lance la commande panoptic
Write-Host "Lancement de panoptic..."
panoptic
