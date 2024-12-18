@echo off

set "ENV_DIR=panoptic_env"
set "MIN_PYTHON_VERSION=3.10"
set "TARGET_PYTHON_VERSION=3.12.7"

:: Fonction d'installation de Python
setlocal
set "PYTHON_INSTALLER=python-installer.exe"
set "PYTHON_DOWNLOAD_URL=https://www.python.org/ftp/python/%TARGET_PYTHON_VERSION%/python-%TARGET_PYTHON_VERSION%-amd64.exe"

install_python() (
    echo Installation de Python version %TARGET_PYTHON_VERSION%...
    powershell -Command "Invoke-WebRequest -Uri %PYTHON_DOWNLOAD_URL% -OutFile %PYTHON_INSTALLER%"
    start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1
    del "%PYTHON_INSTALLER%"
    set "PYTHON_EXEC=python"
    set "PIP_EXEC=pip"
)

:: Vérifie si Python >= 3.10 et pip sont installés
for /f "tokens=*" %%P in ('where python') do (
    set "PYTHON_PATH=%%P"
)
if not defined PYTHON_PATH (
    echo Python n'est pas installé. Téléchargement et installation...
    call :install_python
) else (
    for /f "tokens=*" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"' 2^>nul) do set "PYTHON_VERSION=%%v"
    if %PYTHON_VERSION% GEQ %MIN_PYTHON_VERSION% (
        set "PYTHON_EXEC=python"
        set "PIP_EXEC=pip"
    ) else (
        echo Version de Python obsolète détectée. Mise à jour vers Python %TARGET_PYTHON_VERSION%...
        call :install_python
    )
)

:: Vérifie si l'environnement virtuel existe
if exist "%ENV_DIR%" (
    echo L'environnement "%ENV_DIR%" existe déjà. Activation...
) else (
    echo Création de l'environnement virtuel "%ENV_DIR%"...
    %PYTHON_EXEC% -m venv %ENV_DIR%
    echo Installation de panoptic dans l'environnement virtuel...
    call "%ENV_DIR%\Scripts\activate"
    %PIP_EXEC% install --upgrade pip
    %PIP_EXEC% install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    %PIP_EXEC% install panoptic
)

:: Active l'environnement virtuel
call "%ENV_DIR%\Scripts\activate"

:: Vérifie si une mise à jour de panoptic est disponible et propose de l'installer
for /f "tokens=*" %%v in ('%PIP_EXEC% install panoptic==nonexistent 2^>^&1 ^| findstr /r "from versions: "') do set "LATEST_PANOPTIC_VERSION=%%v"
set "LATEST_PANOPTIC_VERSION=%LATEST_PANOPTIC_VERSION:~15%"
for /f "tokens=*" %%v in ('%PIP_EXEC% show panoptic ^| findstr Version') do set "CURRENT_PANOPTIC_VERSION=%%v"
set "CURRENT_PANOPTIC_VERSION=%CURRENT_PANOPTIC_VERSION:~9%"

if "%LATEST_PANOPTIC_VERSION%" GTR "%CURRENT_PANOPTIC_VERSION%" (
    echo Une nouvelle version de panoptic est disponible : %LATEST_PANOPTIC_VERSION% (actuellement installée : %CURRENT_PANOPTIC_VERSION%).
    set /p "REPLY=Souhaitez-vous installer la dernière version stable ? (o/n): "
    if /i "%REPLY%"=="o" (
        %PIP_EXEC% install -U panoptic
        echo Panoptic mis à jour vers la version %LATEST_PANOPTIC_VERSION%.
    )
) else (
    echo Vous utilisez déjà la dernière version stable de panoptic.
)

:: Lance la commande panoptic
echo Lancement de panoptic...
panoptic
