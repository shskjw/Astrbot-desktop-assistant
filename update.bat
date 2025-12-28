@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: AstrBot Desktop Assistant - Windows 一键更新脚本
:: ============================================================================
:: 特点：
::   1. 只需选择网络环境（海外/国内）
::   2. 自动检测项目目录
::   3. 自动更新代码和依赖
::   4. 显示版本变化
:: ============================================================================

title AstrBot Desktop Assistant 一键更新

:: 颜色定义
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "CYAN=[96m"
set "WHITE=[97m"
set "RESET=[0m"

:: 加速代理列表
set "PROXY_HOSTS=gh.llkk.cc gh-proxy.com mirror.ghproxy.com ghproxy.net"

echo.
echo %CYAN%╔══════════════════════════════════════════════════════════════════════╗%RESET%
echo %CYAN%║                                                                      ║%RESET%
echo %CYAN%║          %WHITE%AstrBot Desktop Assistant 一键更新脚本%CYAN%                      ║%RESET%
echo %CYAN%║                                                                      ║%RESET%
echo %CYAN%╚══════════════════════════════════════════════════════════════════════╝%RESET%
echo.

:: ============================================================================
:: 检测项目目录
:: ============================================================================
echo %CYAN%[1/5]%RESET% 检测项目目录...

set "PROJECT_DIR="

:: 检查当前目录
if exist "%CD%\.git" (
    if exist "%CD%\desktop_client" (
        set "PROJECT_DIR=%CD%"
        goto :project_found
    )
)

:: 检查当前目录下的 Astrbot-desktop-assistant 子目录
if exist "%CD%\Astrbot-desktop-assistant\.git" (
    set "PROJECT_DIR=%CD%\Astrbot-desktop-assistant"
    goto :project_found
)

:: 检查父目录
for %%D in ("%CD%\..") do (
    if exist "%%~fD\.git" (
        if exist "%%~fD\desktop_client" (
            set "PROJECT_DIR=%%~fD"
            goto :project_found
        )
    )
)

:: 未找到项目
echo.
echo %RED%╔══════════════════════════════════════════════════════════════════════╗%RESET%
echo %RED%║  ✗ 未找到 AstrBot Desktop Assistant 项目                             ║%RESET%
echo %RED%╠══════════════════════════════════════════════════════════════════════╣%RESET%
echo %RED%║                                                                      ║%RESET%
echo %RED%║  请确保：                                                            ║%RESET%
echo %RED%║    • 在项目目录中运行此脚本                                          ║%RESET%
echo %RED%║    • 或在包含 Astrbot-desktop-assistant 文件夹的目录中运行           ║%RESET%
echo %RED%║                                                                      ║%RESET%
echo %RED%║  如果尚未安装，请先运行 quick_install.bat                            ║%RESET%
echo %RED%║                                                                      ║%RESET%
echo %RED%╚══════════════════════════════════════════════════════════════════════╝%RESET%
echo.
pause
exit /b 1

:project_found
echo %GREEN%✓ 找到项目目录: !PROJECT_DIR!%RESET%
cd /d "!PROJECT_DIR!"

:: ============================================================================
:: 显示当前版本
:: ============================================================================
echo.
echo %CYAN%[2/5]%RESET% 获取版本信息...

:: 保存当前版本
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%h"`) do set "OLD_COMMIT=%%i"
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%ci"`) do set "OLD_DATE=%%i"
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%s"`) do set "OLD_MSG=%%i"

echo.
echo %WHITE%当前版本：%RESET%
echo   提交: %OLD_COMMIT%
echo   日期: %OLD_DATE%
echo   说明: %OLD_MSG%

:: ============================================================================
:: 选择网络环境
:: ============================================================================
echo.
echo %WHITE%请选择您的网络环境：%RESET%
echo.
echo   %CYAN%[1]%RESET% 我有海外网络环境（可直接访问 GitHub）
echo   %CYAN%[2]%RESET% 我没有海外网络（使用国内加速，推荐大多数用户）
echo.
set /p "NETWORK_CHOICE=请输入选择 [1/2]: "

set "BEST_PROXY="

if "!NETWORK_CHOICE!"=="1" (
    echo.
    echo %GREEN%✓ 将使用 GitHub 直连%RESET%
) else (
    echo.
    echo %CYAN%正在自动测试加速代理，请稍候...%RESET%
    echo.
    
    set "MIN_TIME=9999"
    
    for %%H in (%PROXY_HOSTS%) do (
        echo   测试 %%H ...
        
        ping -n 1 -w 3000 %%H >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            if not defined BEST_PROXY (
                set "BEST_PROXY=%%H"
            )
            echo     %GREEN%✓ 可用%RESET%
        ) else (
            echo     %RED%✗ 不可用%RESET%
        )
    )
    
    if defined BEST_PROXY (
        echo.
        echo %GREEN%✓ 已选择代理: !BEST_PROXY!%RESET%
        
        :: 配置 Git 代理
        git config --local url."https://!BEST_PROXY!/https://github.com".insteadOf "https://github.com"
    ) else (
        echo.
        echo %YELLOW%⚠ 所有代理均不可用，将尝试直连%RESET%
    )
)

:: ============================================================================
:: 更新代码
:: ============================================================================
echo.
echo %CYAN%[3/5]%RESET% 更新代码...

:: 先 fetch
git fetch origin main --depth 1 2>nul
if !ERRORLEVEL! NEQ 0 (
    git fetch origin master --depth 1 2>nul
)

:: 检查是否有更新
git status -uno | findstr /i "behind" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    :: 可能已经是最新，或者 fetch 失败，尝试 pull
    echo 正在拉取最新代码...
)

:: 执行 pull
git pull --rebase 2>nul
if !ERRORLEVEL! NEQ 0 (
    :: 尝试不带 rebase
    git pull 2>nul
    if !ERRORLEVEL! NEQ 0 (
        echo %YELLOW%⚠ 常规更新失败，尝试强制更新...%RESET%
        git fetch origin main --depth 1 2>nul
        git reset --hard origin/main 2>nul
        if !ERRORLEVEL! NEQ 0 (
            git fetch origin master --depth 1 2>nul
            git reset --hard origin/master 2>nul
        )
    )
)

:: 清理代理配置
if defined BEST_PROXY (
    git config --local --unset url."https://!BEST_PROXY!/https://github.com".insteadOf 2>nul
)

:: 获取新版本
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%h"`) do set "NEW_COMMIT=%%i"
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%ci"`) do set "NEW_DATE=%%i"
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%s"`) do set "NEW_MSG=%%i"

echo.
echo %WHITE%更新后版本：%RESET%
echo   提交: %NEW_COMMIT%
echo   日期: %NEW_DATE%
echo   说明: %NEW_MSG%

:: 比较版本
if "%OLD_COMMIT%"=="%NEW_COMMIT%" (
    echo.
    echo %GREEN%✓ 已是最新版本，无需更新%RESET%
) else (
    echo.
    echo %GREEN%✓ 代码已更新 (%OLD_COMMIT% → %NEW_COMMIT%)%RESET%
)

:: ============================================================================
:: 更新依赖
:: ============================================================================
echo.
echo %CYAN%[4/5]%RESET% 更新依赖包...

:: 检测 Python
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
    echo %YELLOW%⚠ 未检测到 Python，跳过依赖更新%RESET%
    goto :skip_deps
)

:: 升级 pip
"!PYTHON_CMD!" -m pip install --upgrade pip -q 2>nul

:: 安装/更新依赖
"!PYTHON_CMD!" -m pip install -r "!PROJECT_DIR!\requirements.txt" -q 2>nul
if !ERRORLEVEL! EQU 0 (
    echo %GREEN%✓ 依赖更新完成%RESET%
) else (
    echo %YELLOW%⚠ 部分依赖更新可能失败%RESET%
)

:skip_deps

:: ============================================================================
:: 完成
:: ============================================================================
echo.
echo %CYAN%[5/5]%RESET% 更新完成！
echo.
echo %GREEN%╔══════════════════════════════════════════════════════════════════════╗%RESET%
echo %GREEN%║                                                                      ║%RESET%
echo %GREEN%║                    ✓ 更新成功！                                      ║%RESET%
echo %GREEN%║                                                                      ║%RESET%
echo %GREEN%╠══════════════════════════════════════════════════════════════════════╣%RESET%
echo %GREEN%║                                                                      ║%RESET%
if "%OLD_COMMIT%"=="%NEW_COMMIT%" (
echo %GREEN%║  状态: 已是最新版本                                                  ║%RESET%
) else (
echo %GREEN%║  版本变化: %OLD_COMMIT% → %NEW_COMMIT%                                           ║%RESET%
)
echo %GREEN%║                                                                      ║%RESET%
echo %GREEN%╚══════════════════════════════════════════════════════════════════════╝%RESET%
echo.

:: 询问是否立即启动
echo 是否立即启动 AstrBot Desktop Assistant？
echo   %CYAN%[1]%RESET% 是
echo   %CYAN%[2]%RESET% 否
echo.
set /p "START_CHOICE=请选择 [1/2]: "

if "!START_CHOICE!"=="1" (
    echo.
    echo 正在启动...
    if defined PYTHON_CMD (
        start "" "!PYTHON_CMD!" -m desktop_client
    ) else (
        if exist "!PROJECT_DIR!\start.bat" (
            start "" "!PROJECT_DIR!\start.bat"
        )
    )
    echo %GREEN%✓ 应用已启动%RESET%
)

echo.
echo %CYAN%感谢使用 AstrBot Desktop Assistant！%RESET%
echo.
pause