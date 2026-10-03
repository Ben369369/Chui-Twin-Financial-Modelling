@echo off
rem Daily data job for Windows Task Scheduler. Runs from the repo root wherever it lives.
rem Needs the user environment variable CHUI_SEC_USER_AGENT ("Name email"), set once with setx.
cd /d "%~dp0.."
if not exist data mkdir data
echo ===== %date% %time% >> data\daily.log
"C:\Users\benon\AppData\Local\Programs\Python\Python312\python.exe" -u scripts\run_daily.py --days 60 >> data\daily.log 2>&1
"C:\Users\benon\AppData\Local\Programs\Python\Python312\python.exe" -u scripts\fill_missing.py --gap 90 >> data\daily.log 2>&1
