@echo off
REM install.bat - Installer for NCSI Resolver
REM This batch file runs the installer script with admin privileges

echo NCSI Resolver Installer
echo =============================================

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

REM Create an alternative installation directory without spaces
set INSTALL_DIR=C:\NCSI_Resolver
echo Installing NCSI Resolver to %INSTALL_DIR%...

REM Run the installer with the alternative path
python installer.py --install --install-dir=%INSTALL_DIR% --quick
if %ERRORLEVEL% neq 0 (
    echo Installation failed. See log for details.
    pause
    exit /b 1
)

echo.
echo NCSI Resolver has been installed successfully!
echo.
echo The service is now running in the background.
echo Windows should now correctly detect your internet connection.
echo.
pause