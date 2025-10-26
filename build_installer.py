#!/usr/bin/env python3
"""
Minimal NSIS builder for NCSI Resolver - Clean Installation
This creates a minimal installer with only essential files
"""

import os
import subprocess
import shutil

def get_version():
    """Get version from version.py"""
    try:
        with open('version.py', 'r') as f:
            content = f.read()
            for line in content.split('\n'):
                if '__version__' in line and '=' in line:
                    return line.split('=')[1].strip().strip('"\'')
    except:
        return "1.0.0"

def create_minimal_nsis_script():
    """Create a minimal NSIS script with only essential files"""
    version = get_version()
    
    script_content = f'''!include "MUI2.nsh"
!include "StrFunc.nsh"
${{StrLoc}}

; Product info
!define PRODUCT_NAME "NCSI Resolver"
!define PRODUCT_VERSION "{version}"

; Installer settings
Name "${{PRODUCT_NAME}}"
OutFile "NCSI_Resolver_v{version}_setup.exe"
InstallDir "$PROGRAMFILES64\\${{PRODUCT_NAME}}"
RequestExecutionLevel admin
ShowInstDetails show

; Interface settings
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Test installation"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchTest

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Language
!insertmacro MUI_LANGUAGE "English"

; Variables
Var PYTHON_EXE

; Main installation section
Section "Install"
    SetOutPath "$INSTDIR"
    
    ; Copy core installer files
    File "installer.py"
    File "service_installer.py"
    File "system_config.py"
    File "firewall_helper.py"
    File "version.py"
    File "nssm.exe"
    
    ; Copy essential NCSI service files directly to root (no subdirectory)
    File "NCSIresolver\\ncsi_server.py"
    File "NCSIresolver\\service_wrapper.py"
    File "NCSIresolver\\config.json"
    File "NCSIresolver\\config_manager.py"
    File "NCSIresolver\\logger.py"
    File "NCSIresolver\\directory_manager.py"
    File "NCSIresolver\\redirect.html"
    
    ; Find Python
    Call FindPython
    
    ; Run installer using the actual installer.py
    DetailPrint "Running NCSI Resolver installer..."
    nsExec::ExecToLog '"$PYTHON_EXE" "$INSTDIR\\installer.py" --install --quick --nobanner'
    Pop $0
    
    ; Also create a separate log file for manual inspection
    ExecWait '"$PYTHON_EXE" "$INSTDIR\\installer.py" --install --quick --nobanner > "$INSTDIR\\install_log.txt" 2>&1' $1
    
    ; Check result
    IntCmp $0 0 success
    MessageBox MB_OK "Installation failed with exit code $0.$\\r$\\nCheck install_log.txt in $INSTDIR for details.$\\r$\\n$\\r$\\nCommon issues:$\\r$\\n- Port 80 may be in use (try --port=8080)$\\r$\\n- Windows Firewall blocking connection$\\r$\\n- Antivirus interference"
    Goto done
    
success:
    DetailPrint "Installation completed successfully"
    Call CreateShortcuts
    Call WriteRegistry
    
done:
SectionEnd

; Find Python function - Future-proof dynamic detection
Function FindPython
    Push $0
    Push $1
    Push $2

    DetailPrint "Searching for Python installation..."

    ; Strategy 1: Try py launcher first (most reliable for getting latest Python)
    StrCpy $PYTHON_EXE "$WINDIR\\py.exe"
    IfFileExists "$PYTHON_EXE" test_python

    ; Strategy 2: Try python.exe in system PATH
    DetailPrint "Checking system PATH for python.exe..."
    nsExec::ExecToStack 'where python.exe'
    Pop $0 ; exit code
    Pop $1 ; output
    IntCmp $0 0 0 try_registry try_registry
    ; Extract first line from where output (in case multiple pythons)
    StrCpy $2 $1 1024 ; Get first 1024 chars
    ; Find first newline and extract path before it
    ${{StrLoc}} $0 $2 "$\\r$\\n" ">"
    IntCmp $0 0 path_found path_found
    StrCpy $PYTHON_EXE $2 $0 ; Extract substring up to newline
    Goto test_python

path_found:
    StrCpy $PYTHON_EXE $2
    Goto test_python

try_registry:
    ; Strategy 3: Enumerate registry for any Python 3.x version (future-proof)
    DetailPrint "Searching Windows registry for Python installations..."

    ; Try Python 3.13 through 3.8 in descending order (prefer newer)
    StrCpy $0 313
registry_loop:
    IntCmp $0 37 registry_done ; Stop at 3.7 (we need 3.8+)

    ; Convert version number to registry format (e.g., 313 -> "3.13")
    IntOp $1 $0 / 10
    IntOp $2 $0 % 10
    StrCpy $1 "$1.$2"

    DetailPrint "Checking registry for Python $1..."

    ; Try HKLM first (system-wide install)
    ReadRegStr $PYTHON_EXE HKLM "SOFTWARE\\Python\\PythonCore\\$1\\InstallPath" "ExecutablePath"
    IfFileExists "$PYTHON_EXE" test_python

    ; Try HKCU (user install)
    ReadRegStr $PYTHON_EXE HKCU "SOFTWARE\\Python\\PythonCore\\$1\\InstallPath" "ExecutablePath"
    IfFileExists "$PYTHON_EXE" test_python

    ; Decrement and try next version
    IntOp $0 $0 - 1
    Goto registry_loop

registry_done:
    ; Strategy 4: Try common installation directories (newest first)
    DetailPrint "Checking standard installation locations..."

    ; System-wide installations (Program Files)
    StrCpy $0 313
dir_loop:
    IntCmp $0 37 user_dir_check

    IntOp $1 $0 / 10
    IntOp $2 $0 % 10
    StrCpy $1 "Python$1$2"

    StrCpy $PYTHON_EXE "$PROGRAMFILES\\$1\\python.exe"
    IfFileExists "$PYTHON_EXE" test_python

    StrCpy $PYTHON_EXE "$PROGRAMFILES32\\$1\\python.exe"
    IfFileExists "$PYTHON_EXE" test_python

    IntOp $0 $0 - 1
    Goto dir_loop

user_dir_check:
    ; User-specific installations
    StrCpy $0 313
user_loop:
    IntCmp $0 37 python_not_found

    IntOp $1 $0 / 10
    IntOp $2 $0 % 10
    StrCpy $1 "Python$1$2"

    StrCpy $PYTHON_EXE "$PROFILE\\AppData\\Local\\Programs\\Python\\$1\\python.exe"
    IfFileExists "$PYTHON_EXE" test_python

    ; Microsoft Store Python location
    StrCpy $PYTHON_EXE "$LOCALAPPDATA\\Microsoft\\WindowsApps\\python.exe"
    IfFileExists "$PYTHON_EXE" test_python

    IntOp $0 $0 - 1
    Goto user_loop

test_python:
    DetailPrint "Found potential Python at: $PYTHON_EXE"
    DetailPrint "Validating Python installation..."

    ; Test if Python actually works and is version 3.8+
    nsExec::ExecToStack '"$PYTHON_EXE" -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"'
    Pop $0 ; exit code
    Pop $1 ; output (unused)

    IntCmp $0 0 python_valid
    DetailPrint "Python validation failed (exit code $0), continuing search..."
    Goto try_registry

python_valid:
    ; Get and display Python version
    nsExec::ExecToStack '"$PYTHON_EXE" --version'
    Pop $0
    Pop $1
    DetailPrint "Python validation successful: $1"
    DetailPrint "Using Python: $PYTHON_EXE"
    Goto found

python_not_found:
    MessageBox MB_ICONSTOP "Python 3.8 or higher not found!$\\r$\\n$\\r$\\nPlease install Python from:$\\r$\\nhttps://www.python.org/downloads/$\\r$\\n$\\r$\\nMake sure to check 'Add Python to PATH' during installation.$\\r$\\n$\\r$\\nAfter installing Python, run this installer again."
    Abort "Python not found"

found:
    Pop $2
    Pop $1
    Pop $0
FunctionEnd

; Create shortcuts
Function CreateShortcuts
    CreateDirectory "$SMPROGRAMS\\NCSI Resolver"

    ; Diagnostics shortcut - run pre-installation checks
    CreateShortCut "$SMPROGRAMS\\NCSI Resolver\\Run Diagnostics.lnk" "$PYTHON_EXE" '"$INSTDIR\\installer.py" --diagnose --nobanner'

    ; Status shortcut - check installation status
    CreateShortCut "$SMPROGRAMS\\NCSI Resolver\\Check Status.lnk" "$PYTHON_EXE" '"$INSTDIR\\installer.py" --check --nobanner'

    ; Uninstaller shortcut - runs the actual installer.py with --uninstall
    CreateShortCut "$SMPROGRAMS\\NCSI Resolver\\Uninstall NCSI Resolver.lnk" "$PYTHON_EXE" '"$INSTDIR\\installer.py" --uninstall --quick --nobanner'

    ; Help shortcut
    FileOpen $0 "$SMPROGRAMS\\NCSI Resolver\\Get Help (GitHub).url" w
    FileWrite $0 "[InternetShortcut]$\\r$\\n"
    FileWrite $0 "URL=https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/discussions$\\r$\\n"
    FileClose $0
FunctionEnd

; Write registry entries
Function WriteRegistry
    WriteRegStr HKLM "Software\\NCSI Resolver" "InstallPath" "$INSTDIR"
    WriteRegStr HKLM "Software\\NCSI Resolver" "Version" "{version}"
    WriteRegStr HKLM "Software\\NCSI Resolver" "PythonPath" "$PYTHON_EXE"
    
    WriteUninstaller "$INSTDIR\\uninstall.exe"
    
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NCSI Resolver" "DisplayName" "NCSI Resolver"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NCSI Resolver" "UninstallString" "$INSTDIR\\uninstall.exe"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NCSI Resolver" "DisplayVersion" "{version}"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NCSI Resolver" "Publisher" "NCSI Resolver Team"
    WriteRegStr HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NCSI Resolver" "URLInfoAbout" "https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX"
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NCSI Resolver" "NoModify" 1
    WriteRegDWORD HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NCSI Resolver" "NoRepair" 1
FunctionEnd

; Test page launcher
Function LaunchTest
    ExecShell "open" "http://localhost/redirect"
FunctionEnd

; Uninstaller
Section "Uninstall"
    ; Get Python path from registry
    ReadRegStr $PYTHON_EXE HKLM "Software\\NCSI Resolver" "PythonPath"
    
    ; Run uninstall script if Python and installer are available
    IfFileExists "$PYTHON_EXE" 0 no_python
    IfFileExists "$INSTDIR\\installer.py" 0 no_installer
    
    DetailPrint "Running NCSI Resolver uninstaller..."
    ExecWait '"$PYTHON_EXE" "$INSTDIR\\installer.py" --uninstall --quick' $0
    Goto cleanup
    
no_python:
    DetailPrint "Python not found, performing manual cleanup..."
    Goto cleanup
    
no_installer:
    DetailPrint "Installer script not found, performing manual cleanup..."
    Goto cleanup
    
cleanup:
    ; Remove all files (thorough cleanup)
    Delete "$INSTDIR\\*.py"
    Delete "$INSTDIR\\*.exe"
    Delete "$INSTDIR\\*.json"
    Delete "$INSTDIR\\*.html"
    Delete "$INSTDIR\\*.txt"
    Delete "$INSTDIR\\*.log"
    Delete "$INSTDIR\\*.reg"
    
    ; Remove any remaining subdirectories
    RMDir /r "$INSTDIR\\__pycache__"
    RMDir /r "$INSTDIR\\Logs"
    RMDir /r "$INSTDIR\\Backups"
    RMDir /r "$INSTDIR\\build"
    RMDir /r "$INSTDIR\\NCSIresolver"
    RMDir /r "$INSTDIR\\scripts"
    
    ; Remove installation directory
    RMDir "$INSTDIR"
    
    ; Remove Start Menu shortcuts
    Delete "$SMPROGRAMS\\NCSI Resolver\\*.lnk"
    Delete "$SMPROGRAMS\\NCSI Resolver\\*.url"
    RMDir "$SMPROGRAMS\\NCSI Resolver"
    
    ; Remove registry entries
    DeleteRegKey HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\NCSI Resolver"
    DeleteRegKey HKLM "Software\\NCSI Resolver"
SectionEnd'''
    
    with open('ncsi_minimal.nsi', 'w') as f:
        f.write(script_content)
    
    print(f"Created ncsi_minimal.nsi for version {version}")

def build_installer():
    """Build with NSIS"""
    nsis_paths = [
        r"C:\\Program Files (x86)\\NSIS\\makensis.exe",
        r"C:\\Program Files\\NSIS\\makensis.exe", 
        "makensis.exe"
    ]
    
    makensis = None
    for path in nsis_paths:
        if os.path.exists(path) or shutil.which(path):
            makensis = path
            break
    
    if not makensis:
        print("NSIS not found. Install from https://nsis.sourceforge.io/")
        return False
    
    print(f"Building with: {makensis}")
    try:
        result = subprocess.run([makensis, "ncsi_minimal.nsi"], 
                              capture_output=True, text=True, check=True)
        print("Build successful!")
        return True
    except subprocess.CalledProcessError as e:
        print("Build failed:")
        print(e.stdout)
        print(e.stderr)
        return False

def main():
    print("NCSI Resolver Minimal NSIS Builder")
    print("=" * 40)
    
    # Check required files exist
    required = [
        'installer.py', 'service_installer.py', 'system_config.py', 
        'firewall_helper.py', 'version.py', 'nssm.exe',
        'NCSIresolver/ncsi_server.py', 'NCSIresolver/service_wrapper.py',
        'NCSIresolver/config.json', 'NCSIresolver/config_manager.py',
        'NCSIresolver/logger.py', 'NCSIresolver/directory_manager.py',
        'NCSIresolver/redirect.html'
    ]
    missing = [f for f in required if not os.path.exists(f)]
    if missing:
        print(f"Missing files: {missing}")
        return 1
    
    create_minimal_nsis_script()
    if build_installer():
        version = get_version()
        print(f"Success! Created: NCSI_Resolver_v{version}_setup.exe")
        print("\\nInstallation will now contain only essential files:")
        print("  - Service files (ncsi_server.py, service_wrapper.py, etc.)")
        print("  - Configuration files (config.json)")
        print("  - System utilities (installer.py, system_config.py)")
        print("  - Service manager (nssm.exe)")
        print("\\nNo duplicate directories or unnecessary files!")
        return 0
    return 1

if __name__ == "__main__":
    exit(main())