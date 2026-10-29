@echo off
setlocal EnableExtensions
REM PPE SAM Multi-Year v0.3.2 - RUN THE APP (recommended)
cd /d "%~dp0"
echo === PPE SAM Multi-Year v0.3.2 ===
call scripts\setup_env.bat
if errorlevel 1 goto :err
echo.
"%VPY%" run_app.py
echo.
echo The app has stopped.
pause
exit /b 0
:err
echo.
echo SETUP FAILED (v0.3.2) - copy the lines above and send them over.
pause
exit /b 1
