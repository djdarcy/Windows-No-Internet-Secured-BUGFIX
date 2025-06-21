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

; Find Python function
Function FindPython
    ; Try registry entries first (most reliable)
    ReadRegStr $PYTHON_EXE HKLM "SOFTWARE\\Python\\PythonCore\\3.10\\InstallPath" "ExecutablePath"
    IfFileExists "$PYTHON_EXE" found
    
    ReadRegStr $PYTHON_EXE HKLM "SOFTWARE\\Python\\PythonCore\\3.9\\InstallPath" "ExecutablePath"
    IfFileExists "$PYTHON_EXE" found
    
    ReadRegStr $PYTHON_EXE HKLM "SOFTWARE\\Python\\PythonCore\\3.8\\InstallPath" "ExecutablePath"
    IfFileExists "$PYTHON_EXE" found
    
    ; Try standard installation locations
    StrCpy $PYTHON_EXE "$PROGRAMFILES\\Python310\\python.exe"
    IfFileExists "$PYTHON_EXE" found
    
    StrCpy $PYTHON_EXE "$PROGRAMFILES\\Python39\\python.exe"
    IfFileExists "$PYTHON_EXE" found
    
    StrCpy $PYTHON_EXE "$PROGRAMFILES\\Python38\\python.exe"
    IfFileExists "$PYTHON_EXE" found
    
    ; Try user installation paths
    StrCpy $PYTHON_EXE "$PROFILE\\AppData\\Local\\Programs\\Python\\Python310\\python.exe"
    IfFileExists "$PYTHON_EXE" found
    
    StrCpy $PYTHON_EXE "$PROFILE\\AppData\\Local\\Programs\\Python\\Python39\\python.exe"
    IfFileExists "$PYTHON_EXE" found
    
    ; Try py launcher (Windows Python Launcher)
    StrCpy $PYTHON_EXE "$WINDIR\\py.exe"
    IfFileExists "$PYTHON_EXE" found
    
    ; Try system PATH
    StrCpy $PYTHON_EXE "python.exe"
    Goto found
    
found:
    DetailPrint "Using Python: $PYTHON_EXE"
FunctionEnd

; Create shortcuts
Function CreateShortcuts
    CreateDirectory "$SMPROGRAMS\\NCSI Resolver"
    
    ; Uninstaller shortcut - runs the actual installer.py with --uninstall
    CreateShortCut "$SMPROGRAMS\\NCSI Resolver\\Uninstall NCSI Resolver.lnk" "$PYTHON_EXE" '"$INSTDIR\\installer.py" --uninstall --quick --nobanner'
    
    ; Diagnostics shortcut - check status
    CreateShortCut "$SMPROGRAMS\\NCSI Resolver\\Check Status.lnk" "$PYTHON_EXE" '"$INSTDIR\\installer.py" --check --nobanner'
    
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