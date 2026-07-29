@echo off
rem Lancement manuel de la veille JO (Option B du plan, R4) : double-clic le matin.
cd /d %~dp0
if not exist .venv\Scripts\python.exe (
    echo [ERREUR] Environnement Python introuvable : suivre la section Installation du fichier INSTALL.md
    pause
    exit /b 1
)
.venv\Scripts\python.exe main.py
if errorlevel 1 (
    echo.
    echo [ECHEC] La veille ne s est pas terminee correctement : consulter le dernier fichier du dossier logs\
) else (
    echo.
    echo [OK] Veille terminee : resultats dans le dossier sorties\
)
pause
