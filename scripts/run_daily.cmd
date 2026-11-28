@echo off
rem Daily data job for Windows Task Scheduler. Runs from the repo root wherever it lives.
rem Needs the user environment variable CHUI_SEC_USER_AGENT ("Name email"), set once with setx.
rem Data lives outside OneDrive (sync locks stalled the job): CHUI_DATA_DIR, else %USERPROFILE%\ChuiData
rem when it exists, else the repo's data\. scripts\backup_data.py copies it back into OneDrive as zips.
cd /d "%~dp0.."
if not defined CHUI_DATA_DIR if exist "%USERPROFILE%\ChuiData\chui.sqlite" set "CHUI_DATA_DIR=%USERPROFILE%\ChuiData"
if not defined CHUI_DATA_DIR set "CHUI_DATA_DIR=%CD%\data"
if not exist "%CHUI_DATA_DIR%" mkdir "%CHUI_DATA_DIR%"
set "PY=C:\Users\benon\AppData\Local\Programs\Python\Python312\python.exe"
set "LOG=%CHUI_DATA_DIR%\daily.log"
echo ===== %date% %time% (data: %CHUI_DATA_DIR%) >> "%LOG%"
"%PY%" -u scripts\run_daily.py --days 60 >> "%LOG%" 2>&1
"%PY%" -u scripts\fill_missing.py --gap 90 --stale 3 >> "%LOG%" 2>&1
"%PY%" -u scripts\backup_data.py >> "%LOG%" 2>&1
