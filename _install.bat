@echo off
SETLOCAL EnableDelayedExpansion

REM install.bat - Installer for NCSI Resolver
REM This batch file runs the installer script with admin privileges

echo NCSI Resolver Installer
echo =============================================
@REM echo Usage: _install.bat [install-directory] [installer.py flags, see --help or -h]
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

REM  Change to the directory where this script is located
cd /d "%~dp0"

REM Prepare the command line
SET CMD=python installer.py --install --verbose

REM Check if install directory was passed as parameter
if "%~1" NEQ "" (
    REM Check if the parameter doesn't start with - or / (likely a directory)
    set FIRST_CHAR=%~1
    set FIRST_CHAR=!FIRST_CHAR:~0,1!
    
    if "!FIRST_CHAR!" NEQ "-" if "!FIRST_CHAR!" NEQ "/" (
        REM First parameter is used as installation directory
        echo Installing to custom directory: %~1
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

REM Run the installer with the constructed command line
echo Running: !CMD!
!CMD!

REM Check installation
echo.
echo Verifying installation...
if defined INSTALL_DIR (
    python installer.py --check --install-dir="!INSTALL_DIR!" --nobanner
) else (
    python installer.py --check --nobanner
)

echo.
echo Installation process completed.
echo If there are any issues, please check the logs in the installation directory.
echo.
pause
exit /b 0

:show_help
echo.
echo This script installs the NCSI Resolver with administrator privileges.
echo.
echo Usage: _install.bat [install-directory] [installer.py flags]
echo.
echo Options:
echo   [install-directory]    Optional: Directory where NCSI Resolver will be installed
echo                          If not specified, defaults from config.json will be used
echo.
echo   [installer.py flags]   Optional: Any additional flags to pass to installer.py
echo                          For example: --port=8080 --debug
echo.
echo Examples:
echo   _install.bat                     - Install using defaults
echo   _install.bat "C:\My Folder"      - Install to specified directory
echo   _install.bat --port=8080         - Install with custom port
echo   _install.bat "C:\Path" --debug   - Install to directory with debug logging
echo.
pause
exit /b 0

ENDLOCAL