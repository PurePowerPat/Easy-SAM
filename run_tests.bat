@echo off
setlocal EnableExtensions
REM PPE SAM Multi-Year v0.3.1 - run the automated tests
cd /d "%~dp0"
call scripts\setup_env.bat
if errorlevel 1 goto :err
"%VPY%" tests\test_pipeline.py || goto :err
"%VPY%" tests\test_server.py || goto :err
"%VPY%" tests\test_weather.py || goto :err
"%VPY%" tests\test_real_libraries.py || goto :err
echo ALL TESTS PASSED (v0.3.1)
pause
exit /b 0
:err
echo TESTS FAILED (v0.3.1)
pause
exit /b 1
