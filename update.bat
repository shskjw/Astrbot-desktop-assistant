@echo off
setlocal EnableDelayedExpansion

:: ============================================================================
:: AstrBot Desktop Assistant - Windows Update Script
:: ============================================================================
:: Features:
::   1. Dual update modes: Git (latest) / Release (stable)
::   2. Network environment selection (Direct/Proxy)
::   3. Auto-detect project directory (supports ZIP installation)
::   4. Auto-update code and dependencies
::   5. Show version changes
:: ============================================================================
:: Usage:
::   update.bat                    - Default: Git mode for latest code
::   update.bat git                - Git mode for latest code
::   update.bat release v1.0.0     - Release mode for specific version
:: ============================================================================

title AstrBot Desktop Assistant Update

:: Parse command line arguments
set "UPDATE_MODE=git"
set "TARGET_VERSION="

if not "%~1"=="" (
    set "UPDATE_MODE=%~1"
)
if not "%~2"=="" (
    set "TARGET_VERSION=%~2"
)

:: Validate arguments
if /i "!UPDATE_MODE!"=="release" (
    if "!TARGET_VERSION!"=="" (
        echo.
        echo X Error: Release mode requires version number
        echo Usage: update.bat release v1.0.0
        echo.
        pause
        exit /b 1
    )
)

:: Proxy list for China users
set "PROXY_HOSTS=gh.llkk.cc gh-proxy.com mirror.ghproxy.com ghproxy.net"

echo.
echo ======================================================================
echo         AstrBot Desktop Assistant Update Script
echo ======================================================================
echo.

:: Display update mode
if /i "!UPDATE_MODE!"=="release" (
    echo ! Update Mode: Release - Stable - Target: !TARGET_VERSION!
) else (
    echo + Update Mode: Git - Latest
)
echo.

:: ============================================================================
:: Detect project directory
:: ============================================================================
echo Step 1 of 5 - Detecting project directory...

set "PROJECT_DIR="
set "HAS_GIT=0"

:: Check current directory - with .git
if exist "%CD%\.git" (
    if exist "%CD%\desktop_client" (
        set "PROJECT_DIR=%CD%"
        set "HAS_GIT=1"
        goto :project_found
    )
)

:: Check current directory - without .git (ZIP installation)
if exist "%CD%\desktop_client" (
    if exist "%CD%\requirements.txt" (
        set "PROJECT_DIR=%CD%"
        set "HAS_GIT=0"
        goto :project_found
    )
)

:: Check Astrbot-desktop-assistant subdirectory - with .git
if exist "%CD%\Astrbot-desktop-assistant\.git" (
    set "PROJECT_DIR=%CD%\Astrbot-desktop-assistant"
    set "HAS_GIT=1"
    goto :project_found
)

:: Check Astrbot-desktop-assistant subdirectory - without .git
if exist "%CD%\Astrbot-desktop-assistant\desktop_client" (
    set "PROJECT_DIR=%CD%\Astrbot-desktop-assistant"
    set "HAS_GIT=0"
    goto :project_found
)

:: Check Astrbot-desktop-assistant-main subdirectory (GitHub ZIP default name)
if exist "%CD%\Astrbot-desktop-assistant-main\.git" (
    set "PROJECT_DIR=%CD%\Astrbot-desktop-assistant-main"
    set "HAS_GIT=1"
    goto :project_found
)

if exist "%CD%\Astrbot-desktop-assistant-main\desktop_client" (
    set "PROJECT_DIR=%CD%\Astrbot-desktop-assistant-main"
    set "HAS_GIT=0"
    goto :project_found
)

:: Check parent directory
for %%D in ("%CD%\..") do (
    if exist "%%~fD\.git" (
        if exist "%%~fD\desktop_client" (
            set "PROJECT_DIR=%%~fD"
            set "HAS_GIT=1"
            goto :project_found
        )
    )
    if exist "%%~fD\desktop_client" (
        if exist "%%~fD\requirements.txt" (
            set "PROJECT_DIR=%%~fD"
            set "HAS_GIT=0"
            goto :project_found
        )
    )
)

:: Project not found
echo.
echo ======================================================================
echo   X Project not found: AstrBot Desktop Assistant
echo ======================================================================
echo.
echo Please ensure:
echo   - Run this script in the project directory
echo   - Or in a directory containing Astrbot-desktop-assistant folder
echo.
echo If not installed yet, run quick_install.bat first
echo.
pause
exit /b 1

:project_found
echo + Found project: !PROJECT_DIR!

:: Check if Git is available
if "!HAS_GIT!"=="0" (
    echo ! No .git directory found - ZIP installation detected
    echo.
    echo Options:
    echo   1 - Initialize Git repository - recommended for future updates
    echo   2 - Skip update - manual download required
    echo.
    set /p "GIT_CHOICE=Select 1 or 2: "
    
    if "!GIT_CHOICE!"=="1" (
        echo.
        echo Initializing Git repository...
        cd /d "!PROJECT_DIR!"
        
        git --version >nul 2>&1
        if !ERRORLEVEL! NEQ 0 (
            echo X Git is not installed. Please install Git first.
            echo   Download: https://git-scm.com/download/win
            pause
            exit /b 1
        )
        
        git init >nul 2>&1
        git remote add origin https://github.com/muyouzhi6/Astrbot-desktop-assistant.git >nul 2>&1
        git fetch origin main --depth 1 >nul 2>&1
        if !ERRORLEVEL! NEQ 0 (
            git fetch origin master --depth 1 >nul 2>&1
        )
        
        echo + Git repository initialized
        set "HAS_GIT=1"
    ) else (
        echo.
        echo ! Skipping update. Please download the latest version manually:
        echo   https://github.com/muyouzhi6/Astrbot-desktop-assistant/releases
        echo.
        goto :skip_to_deps
    )
)

cd /d "!PROJECT_DIR!"

:: ============================================================================
:: Get current version
:: ============================================================================
echo.
echo Step 2 of 5 - Getting version info...

:: Save current version
set "OLD_COMMIT=unknown"
set "OLD_DATE=unknown"
set "OLD_MSG=unknown"

for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%h" 2^>nul`) do set "OLD_COMMIT=%%i"
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%ci" 2^>nul`) do set "OLD_DATE=%%i"
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%s" 2^>nul`) do set "OLD_MSG=%%i"

echo.
echo Current Version:
echo   Commit: %OLD_COMMIT%
echo   Date: %OLD_DATE%
echo   Message: %OLD_MSG%

:: ============================================================================
:: Select network environment
:: ============================================================================
echo.
echo Select your network environment:
echo.
echo   1 - Direct access to GitHub - overseas network
echo   2 - Use proxy - recommended for China users
echo.
set /p "NETWORK_CHOICE=Select 1 or 2: "

set "BEST_PROXY="

if "!NETWORK_CHOICE!"=="1" (
    echo.
    echo + Using direct GitHub connection
) else (
    echo.
    echo Testing proxy servers, please wait...
    echo.
    
    set "MIN_TIME=9999"
    
    for %%H in (%PROXY_HOSTS%) do (
        echo   Testing %%H ...
        
        ping -n 1 -w 3000 %%H >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            if not defined BEST_PROXY (
                set "BEST_PROXY=%%H"
            )
            echo     + Available
        ) else (
            echo     X Unavailable
        )
    )
    
    if defined BEST_PROXY (
        echo.
        echo + Selected proxy: !BEST_PROXY!
        
        :: Configure Git proxy
        git config --local url."https://!BEST_PROXY!/https://github.com".insteadOf "https://github.com"
    ) else (
        echo.
        echo ! All proxies unavailable, trying direct connection
    )
)

:: ============================================================================
:: Update code
:: ============================================================================
echo.
echo Step 3 of 5 - Updating code...

if /i "!UPDATE_MODE!"=="release" (
    :: ========================================================================
    :: Release mode: switch to specific version tag
    :: ========================================================================
    echo Fetching version tags...
    git fetch --tags 2>nul
    if !ERRORLEVEL! NEQ 0 (
        echo X Failed to fetch tags
        goto :update_failed
    )
    
    :: Check if target version exists
    git tag -l "!TARGET_VERSION!" | findstr /r "." >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo X Version !TARGET_VERSION! not found
        echo.
        echo Available versions:
        for /f "tokens=*" %%t in ('git tag -l --sort^=-v:refname 2^>nul') do (
            echo   %%t
        )
        goto :update_failed
    )
    
    :: Switch to specified version
    echo Switching to version !TARGET_VERSION!...
    git checkout "!TARGET_VERSION!" 2>nul
    if !ERRORLEVEL! NEQ 0 (
        echo ! Switch failed, trying force checkout...
        git checkout -f "!TARGET_VERSION!" 2>nul
        if !ERRORLEVEL! NEQ 0 (
            echo X Failed to switch version
            goto :update_failed
        )
    )
    
    echo + Switched to version !TARGET_VERSION!
    
) else (
    :: ========================================================================
    :: Git mode: pull latest code
    :: ========================================================================
    :: First fetch
    git fetch origin main --depth 1 2>nul
    if !ERRORLEVEL! NEQ 0 (
        git fetch origin master --depth 1 2>nul
    )

    :: Check for updates
    git status -uno | findstr /i "behind" >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        echo Pulling latest code...
    )

    :: Execute pull
    git pull --rebase 2>nul
    if !ERRORLEVEL! NEQ 0 (
        :: Try without rebase
        git pull 2>nul
        if !ERRORLEVEL! NEQ 0 (
            echo ! Normal update failed, trying force update...
            git fetch origin main --depth 1 2>nul
            git reset --hard origin/main 2>nul
            if !ERRORLEVEL! NEQ 0 (
                git fetch origin master --depth 1 2>nul
                git reset --hard origin/master 2>nul
            )
        )
    )
)

:: Clean up proxy configuration
if defined BEST_PROXY (
    git config --local --unset url."https://!BEST_PROXY!/https://github.com".insteadOf 2>nul
)

:: Get new version
set "NEW_COMMIT=unknown"
set "NEW_DATE=unknown"
set "NEW_MSG=unknown"

for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%h" 2^>nul`) do set "NEW_COMMIT=%%i"
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%ci" 2^>nul`) do set "NEW_DATE=%%i"
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%s" 2^>nul`) do set "NEW_MSG=%%i"

:: Get current tag (if any)
set "NEW_TAG="
for /f "usebackq tokens=*" %%i in (`git describe --tags --exact-match 2^>nul`) do set "NEW_TAG=%%i"

echo.
echo Updated Version:
echo   Commit: %NEW_COMMIT%
if defined NEW_TAG echo   Tag: %NEW_TAG%
echo   Date: %NEW_DATE%
echo   Message: %NEW_MSG%

:: Compare versions
if "%OLD_COMMIT%"=="%NEW_COMMIT%" (
    echo.
    echo + Already up to date, no update needed
) else (
    echo.
    echo + Code updated: %OLD_COMMIT% to %NEW_COMMIT%
)

goto :update_deps

:update_failed
echo.
echo X Update failed. Please check network connection or version number
:: Clean up proxy configuration
if defined BEST_PROXY (
    git config --local --unset url."https://!BEST_PROXY!/https://github.com".insteadOf 2>nul
)
pause
exit /b 1

:skip_to_deps
cd /d "!PROJECT_DIR!"

:update_deps

:: ============================================================================
:: Update dependencies
:: ============================================================================
echo.
echo Step 4 of 5 - Updating dependencies...

:: Detect Python
set "PYTHON_CMD="

if exist "!PROJECT_DIR!\venv\Scripts\python.exe" (
    set "PYTHON_CMD=!PROJECT_DIR!\venv\Scripts\python.exe"
) else (
    python --version >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "PYTHON_CMD=python"
    ) else (
        py --version >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            set "PYTHON_CMD=py"
        )
    )
)

if not defined PYTHON_CMD (
    echo ! Python not detected, skipping dependency update
    goto :skip_deps
)

:: Upgrade pip
"!PYTHON_CMD!" -m pip install --upgrade pip -q 2>nul

:: Install/update dependencies
"!PYTHON_CMD!" -m pip install -r "!PROJECT_DIR!\requirements.txt" -q 2>nul
if !ERRORLEVEL! EQU 0 (
    echo + Dependencies updated successfully
) else (
    echo ! Some dependencies may have failed to update
)

:skip_deps

:: ============================================================================
:: Complete
:: ============================================================================
echo.
echo Step 5 of 5 - Update complete!
echo.
echo ======================================================================
echo                     + Update Successful!
echo ======================================================================
echo.
if /i "!UPDATE_MODE!"=="release" (
echo   Mode: Release - Stable
echo   Target: !TARGET_VERSION!
) else (
echo   Mode: Git - Latest
)
if "%OLD_COMMIT%"=="%NEW_COMMIT%" (
echo   Status: Already up to date
) else (
echo   Changed: %OLD_COMMIT% to %NEW_COMMIT%
)
echo.

:: Ask whether to start immediately
echo Start AstrBot Desktop Assistant now?
echo   1 - Yes
echo   2 - No
echo.
set /p "START_CHOICE=Select 1 or 2: "

if "!START_CHOICE!"=="1" (
    echo.
    echo Starting...
    if defined PYTHON_CMD (
        start "" "!PYTHON_CMD!" -m desktop_client
    ) else (
        if exist "!PROJECT_DIR!\start.bat" (
            start "" "!PROJECT_DIR!\start.bat"
        )
    )
    echo + Application started
)

echo.
echo Thank you for using AstrBot Desktop Assistant!
echo.
pause