@echo off
setlocal EnableExtensions
REM PPE SAM Multi-Year - build the standalone .exe (optional; may be blocked by company policy)
cd /d "%~dp0"
call scripts\setup_env.bat
if errorlevel 1 goto :err
"%VPY%" -m pip install pyinstaller -r requirements-dev.txt --disable-pip-version-check -q
if errorlevel 1 goto :err
"%VPY%" -m pytest -q
if errorlevel 1 goto :err
"%VPY%" -m PyInstaller --noconfirm --clean --name PPE_SAM_MultiYear --console --collect-all PySAM ^
  --add-data "ppe_sam\static;ppe_sam\static" --add-data "ppe_sam\data;ppe_sam\data" --add-data "libraries;libraries" run_app.py
if errorlevel 1 goto :err
echo BUILD SUCCEEDED: %CD%\dist\PPE_SAM_MultiYear\PPE_SAM_MultiYear.exe
pause
exit /b 0
:err
echo BUILD FAILED
pause
exit /b 1
