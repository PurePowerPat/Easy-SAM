@echo off
setlocal EnableExtensions
REM PPE SAM Multi-Year - double-clicking an .esam project file opens it in this copy of the app.
REM For the current Windows user only (no admin rights). Run it again after moving this folder.
REM register_esam.bat /u removes it.
cd /d "%~dp0"
set "ACT=--register"
if /i "%~1"=="/u" set "ACT=--unregister"
call scripts\setup_env.bat
if errorlevel 1 goto :err
"%VPY%" run_app.py %ACT%
if errorlevel 1 goto :err
pause
exit /b 0
:err
echo.
echo FAILED - copy the lines above and send them over.
pause
exit /b 1
