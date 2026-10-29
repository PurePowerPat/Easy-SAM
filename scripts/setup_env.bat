@echo off
REM PPE SAM Multi-Year - shared environment setup (v0.3.3). Sets VPY to the project's .venv python.
set "PYLAUNCH="
for %%V in (3.14 3.13 3.12) do (
  if not defined PYLAUNCH (
    py -%%V -c "import sys" >nul 2>&1 && set "PYLAUNCH=py -%%V"
  )
)
if not defined PYLAUNCH (
  echo ERROR: Python 3.14 was not found. Install it with:  py install 3.14
  exit /b 1
)
set "VPY=%CD%\.venv\Scripts\python.exe"
if exist "%VPY%" (
  "%VPY%" -c "import sys; sys.exit(0 if (3,8) <= sys.version_info[:2] <= (3,14) else 1)"
  if errorlevel 1 (
    echo Existing .venv uses an unsupported Python version - recreating it.
    rmdir /s /q .venv
  )
)
if not exist "%VPY%" (
  echo First-time setup: creating .venv with %PYLAUNCH% ...
  %PYLAUNCH% -m venv .venv
  if errorlevel 1 exit /b 1
)
if not exist "%VPY%" (
  echo ERROR: .venv was not created.
  exit /b 1
)
"%VPY%" -c "import PySAM.Pvsamv1" >nul 2>&1
if errorlevel 1 (
  echo Installing NLR-PySAM 8.0.0 into .venv ...
  "%VPY%" -m pip install --upgrade pip --disable-pip-version-check -q
  "%VPY%" -m pip install -r requirements.txt --disable-pip-version-check
  if errorlevel 1 exit /b 1
)
"%VPY%" -c "import sys, PySAM.Pvsamv1; print('Python', sys.version.split()[0], '+ PySAM OK')"
if errorlevel 1 exit /b 1
if not exist libraries mkdir libraries
set "BASE=https://raw.githubusercontent.com/NatLabRockies/SAM/cba319ded1c32a7f5b3ac76545a29e1f7181d238/deploy/libraries"
if not exist "libraries\CEC Modules.csv" (
  echo Downloading CEC Modules.csv ...
  curl -L -f -s -o "libraries\CEC Modules.csv" "%BASE%/CEC%%20Modules.csv"
  if errorlevel 1 exit /b 1
)
if not exist "libraries\CEC Inverters.csv" (
  echo Downloading CEC Inverters.csv ...
  curl -L -f -s -o "libraries\CEC Inverters.csv" "%BASE%/CEC%%20Inverters.csv"
  if errorlevel 1 exit /b 1
)
exit /b 0
