@echo off

REM Vérifier si la commande uv est disponible, sinon installer uv
set "Path=%userprofile%\.local\bin;%Path%"
where uv >nul 2>&1
if errorlevel 1 (
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    set "Path=%userprofile%\.local\bin;%Path%"
)

REM changer de disque si nécessaire
%userprofile:~0,1%:

REM Aller dans le dossier utilisateur
cd %userprofile%

REM Créer le dossier panoptic s'il n'existe pas
if not exist panoptic (
    mkdir panoptic
)
cd panoptic

REM Créer un environnement virtuel avec Python 3.12
if not exist .venv (
    uv venv --python 3.12
)

REM Installer pip 
uv pip install pip

REM Vérifier si panoptic est installé, sinon l'installer
uv pip show panoptic >nul 2>&1
if errorlevel 1 (
    uv pip install panoptic
)

REM Vérifier si panoptic est obsolète et demander à l'utilisateur pour une mise à jour
uv pip list --outdated | findstr panoptic >nul 2>&1

echo Recherche de mise a jour

if %errorlevel%==0 (
    echo "Mise a jour trouvee, voulez vous l'installer? (O/N)"
    set /p userInput=
    if /i "%userInput%"=="O" (
        uv pip install -U panoptic
    )
) else (
    echo La derniere version de panoptic est deja installee.
)

echo Lancement de panoptic...

REM Activer l'environnement virtuel et lancer panoptic
call .venv\Scripts\activate
call .venv\Scripts\panoptic
