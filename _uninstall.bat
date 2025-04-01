@echo off
SETLOCAL EnableDelayedExpansion

REM uninstall.bat - Uninstaller for NCSI Resolver
REM This batch file runs the uninstaller script with admin privileges

echo NCSI Resolver Uninstaller
echo =============================================
@REM echo Usage: _uninstall.bat [install-directory] [installer.py flags, see --help or -h]
@REM echo =============================================

REM Check for help flags
if "%~1"=="-h" goto :show_help
if "%~1"=="--help" goto :show_help
if "%~1"=="/?" goto :show_help

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

REM Prepare the command line
SET CMD=python installer.py --uninstall --verbose

REM Check if install directory was passed as parameter
if "%~1" NEQ "" (
    REM Check if the parameter doesn't start with - or / (likely a directory)
    set FIRST_CHAR=%~1
    set FIRST_CHAR=!FIRST_CHAR:~0,1!
    
    if "!FIRST_CHAR!" NEQ "-" if "!FIRST_CHAR!" NEQ "/" (
        REM First parameter is used as installation directory
        echo Uninstalling from custom directory: %~1
        SET INSTALL_DIR=%~1
        SET CMD=!CMD! --install-dir="%~1"
        
        REM Shift parameters for additional processing
        SHIFT
    )
) else (
    echo Using default installation directory from config.json
)

REM Add any additional parameters
:param_loop
if "%~1" NEQ "" (
    SET CMD=!CMD! %1
    SHIFT
    goto :param_loop
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

REM Run the uninstaller with the constructed command line
echo.
echo Uninstalling NCSI Resolver...
echo Running: !CMD!
!CMD!
if %ERRORLEVEL% neq 0 (
    echo Uninstallation failed. See log for details.
)

REM Verify service is removed
echo.
echo Verifying service removal...
python installer.py --check --nobanner

echo.
echo Uninstallation process completed.
echo The service has been removed and Windows has been restored to default network detection behavior.
echo.
pause
exit /b 0

:show_help
echo.
echo This script uninstalls the NCSI Resolver with administrator privileges.
echo.
echo Usage: _uninstall.bat [install-directory] [installer.py flags]
echo.
echo Options:
echo   [install-directory]    Optional: Directory where NCSI Resolver is installed
echo                          If not specified, defaults from config.json will be used
echo.
echo   [installer.py flags]   Optional: Any additional flags to pass to installer.py
echo                          For example: --debug
echo.
echo Examples:
echo   _uninstall.bat                     - Uninstall using defaults
echo   _uninstall.bat "C:\My Folder"      - Uninstall from specified directory
echo   _uninstall.bat --debug             - Uninstall with debug logging
echo.
pause
exit /b 0

ENDLOCAL