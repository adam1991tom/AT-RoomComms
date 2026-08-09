@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo  AT RoomComms Client MSI Builder - Diagnostic Mode
echo ============================================================
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build-MSI.ps1"
set "BUILD_EXIT=%ERRORLEVEL%"
echo.
echo ============================================================
if "%BUILD_EXIT%"=="0" (
  echo BUILD COMPLETED SUCCESSFULLY
) else (
  echo BUILD FAILED WITH EXIT CODE %BUILD_EXIT%
  echo Check the installer\Logs folder for the complete log.
)
echo ============================================================
echo.
pause
exit /b %BUILD_EXIT%
