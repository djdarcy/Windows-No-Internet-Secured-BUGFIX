@echo off
REM uninstall.bat - Uninstaller for NCSI Resolver
REM This batch file runs the uninstaller script with admin privileges

echo NCSI Resolver Uninstaller
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

REM Confirm uninstallation
echo This will completely remove NCSI Resolver from your system.
echo All settings will be restored to Windows defaults.
echo.
set /p CONFIRM="Are you sure you want to continue? (Y/N): "
if /i "%CONFIRM%" neq "Y" (
    echo Uninstallation cancelled.
    pause
    exit /b 0
)

REM Run the uninstaller
echo Uninstalling NCSI Resolver...
python installer.py --uninstall --quick
if %ERRORLEVEL% neq 0 (
    echo Uninstallation failed. See log for details.
    pause
    exit /b 1
)

echo.
echo NCSI Resolver has been successfully uninstalled.
echo.
echo Windows has been restored to default network detection behavior.
echo.
pause