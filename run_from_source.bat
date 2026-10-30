@echo off
setlocal EnableExtensions
REM PPE SAM Multi-Year - RUN THE APP (recommended). The app prints its version when it starts.
REM With a file (run_from_source.bat project.esam, or a double-clicked .esam once register_esam.bat ran) it opens it.
set "ESAM_FILE=%~f1"
cd /d "%~dp0"
echo === PPE SAM Multi-Year ===
call scripts\setup_env.bat
if errorlevel 1 goto :err
echo.
if defined ESAM_FILE goto :open
"%VPY%" run_app.py
goto :stopped
:open
"%VPY%" run_app.py "%ESAM_FILE%"
REM 3 = the file went to the app that was already running: nothing more to show here.
if "%ERRORLEVEL%"=="3" exit /b 0
:stopped
echo.
echo The app has stopped.
pause
exit /b 0
:err
echo.
echo SETUP FAILED - copy the lines above and send them over.
pause
exit /b 1
