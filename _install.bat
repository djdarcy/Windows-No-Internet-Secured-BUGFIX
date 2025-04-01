@echo off
SETLOCAL

REM install.bat - Installer for NCSI Resolver
REM This batch file runs the installer script with admin privileges

echo NCSI Resolver Installer
echo =============================================

REM Check if install directory was passed as parameter
if "%~1"=="" (
    set INSTALL_DIR=C:\NCSI_Resolver
) else (
    set INSTALL_DIR=%~1
)

REM Check for admin privileges
NET SESSION >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Administrator privileges required.
    echo Right-click and select "Run as administrator".
    pause
    exit /b 1
)

REM Check if Python is installed
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python is not installed or not in PATH.
    echo Please install Python 3.6 or higher.
    pause
    exit /b 1
)


REM Run the installer with admin privileges and the alternative path
echo Installing NCSI Resolver to %INSTALL_DIR%...
python installer.py --install --install-dir="%INSTALL_DIR%" --verbose

REM Check installation
echo.
echo Verifying installation...
python installer.py --check --install-dir="%INSTALL_DIR%" --nobanner

echo.
echo Installation process completed.
echo If there are any issues, please check the logs in the installation directory.
echo.
pause
ENDLOCAL