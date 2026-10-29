@echo off
setlocal EnableExtensions
REM PPE SAM Multi-Year - run the automated tests (pytest; offline except the first-time install)
cd /d "%~dp0"
call scripts\setup_env.bat
if errorlevel 1 goto :err
"%VPY%" -c "import pytest" >nul 2>&1
if errorlevel 1 (
  echo Installing the test tools into .venv ...
  "%VPY%" -m pip install -r requirements-dev.txt --disable-pip-version-check -q
  if errorlevel 1 goto :err
)
"%VPY%" -m pytest
if errorlevel 1 goto :err
echo ALL TESTS PASSED
pause
exit /b 0
:err
echo TESTS FAILED
pause
exit /b 1
