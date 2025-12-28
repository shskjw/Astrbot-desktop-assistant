@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: ============================================================================
:: AstrBot Desktop Assistant - Windows 傻瓜式一键安装脚本
:: ============================================================================
:: 特点：
::   1. 只需选择网络环境（海外/国内）
::   2. 自动测试并选择最快的加速代理
::   3. 全自动完成所有安装步骤
::   4. 自动创建桌面快捷方式和开机自启
:: ============================================================================

title AstrBot Desktop Assistant 一键安装

:: 颜色定义
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "CYAN=[96m"
set "WHITE=[97m"
set "RESET=[0m"

:: GitHub 仓库地址
set "GITHUB_REPO=https://github.com/muyouzhi6/Astrbot-desktop-assistant.git"

:: 加速代理列表（使用 ping 测试）
set "PROXY_HOSTS=gh.llkk.cc gh-proxy.com mirror.ghproxy.com ghproxy.net"

echo.
echo %CYAN%╔══════════════════════════════════════════════════════════════════════╗%RESET%
echo %CYAN%║                                                                      ║%RESET%
echo %CYAN%║          %WHITE%AstrBot Desktop Assistant 一键安装脚本%CYAN%                      ║%RESET%
echo %CYAN%║                                                                      ║%RESET%
echo %CYAN%║          %GREEN%✓ 傻瓜式安装，只需一个选择！%CYAN%                                ║%RESET%
echo %CYAN%║                                                                      ║%RESET%
echo %CYAN%╚══════════════════════════════════════════════════════════════════════╝%RESET%
echo.

:: ============================================================================
:: 唯一的用户选择：网络环境
:: ============================================================================
echo %WHITE%请选择您的网络环境：%RESET%
echo.
echo   %CYAN%[1]%RESET% 我有海外网络环境（可直接访问 GitHub）
echo   %CYAN%[2]%RESET% 我没有海外网络（使用国内加速，推荐大多数用户）
echo.
set /p "NETWORK_CHOICE=请输入选择 [1/2]: "

if "!NETWORK_CHOICE!"=="1" (
    set "USE_PROXY=0"
    echo.
    echo %GREEN%✓ 将使用 GitHub 直连%RESET%
) else (
    set "USE_PROXY=1"
    echo.
    echo %CYAN%正在自动测试加速代理，请稍候...%RESET%
)

set "CLONE_URL=%GITHUB_REPO%"
set "BEST_PROXY="

:: ============================================================================
:: 自动测试代理延迟（使用 ping）
:: ============================================================================
if "!USE_PROXY!"=="1" (
    echo.
    set "MIN_TIME=9999"
    
    for %%H in (%PROXY_HOSTS%) do (
        echo   测试 %%H ...
        
        :: 使用 ping 测试，提取平均延迟
        for /f "tokens=*" %%R in ('ping -n 1 -w 3000 %%H 2^>nul ^| findstr /i "平均 Average"') do (
            set "PING_RESULT=%%R"
        )
        
        :: 提取延迟数值
        set "LATENCY=9999"
        for /f "tokens=*" %%L in ('ping -n 1 -w 3000 %%H 2^>nul ^| findstr /i "时间=" ^| findstr /r "[0-9]*ms"') do (
            for /f "tokens=2 delims==" %%T in ("%%L") do (
                for /f "tokens=1 delims=m" %%M in ("%%T") do (
                    set "LATENCY=%%M"
                )
            )
        )
        
        :: 备用方法：检测是否能 ping 通
        ping -n 1 -w 3000 %%H >nul 2>&1
        if !ERRORLEVEL! EQU 0 (
            if !LATENCY! LSS !MIN_TIME! (
                set "MIN_TIME=!LATENCY!"
                set "BEST_PROXY=%%H"
                echo     %GREEN%✓ 可用 (!LATENCY! ms)%RESET%
            ) else (
                echo     %GREEN%✓ 可用%RESET%
            )
        ) else (
            echo     %RED%✗ 不可用%RESET%
        )
    )
    
    if defined BEST_PROXY (
        echo.
        echo %GREEN%✓ 已选择最快代理: !BEST_PROXY!%RESET%
        set "CLONE_URL=https://!BEST_PROXY!/!GITHUB_REPO!"
    ) else (
        echo.
        echo %YELLOW%⚠ 所有代理均不可用，将尝试直连 GitHub%RESET%
        set "CLONE_URL=%GITHUB_REPO%"
    )
)

:: ============================================================================
:: 检测 Git
:: ============================================================================
echo.
echo %CYAN%[1/6]%RESET% 检测 Git 环境...

git --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo %RED%╔══════════════════════════════════════════════════════════════════════╗%RESET%
    echo %RED%║  ✗ 未检测到 Git，请先安装 Git 后重试                                 ║%RESET%
    echo %RED%╠══════════════════════════════════════════════════════════════════════╣%RESET%
    echo %RED%║                                                                      ║%RESET%
    echo %RED%║  下载地址：https://git-scm.com/downloads                             ║%RESET%
    echo %RED%║                                                                      ║%RESET%
    echo %RED%║  安装时保持默认选项即可                                              ║%RESET%
    echo %RED%║                                                                      ║%RESET%
    echo %RED%╚══════════════════════════════════════════════════════════════════════╝%RESET%
    echo.
    pause
    exit /b 1
)
echo %GREEN%✓ Git 已安装%RESET%

:: ============================================================================
:: 检测 Python
:: ============================================================================
echo.
echo %CYAN%[2/6]%RESET% 检测 Python 环境...

set "PYTHON_CMD="

:: 尝试多种方式查找 Python
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
    goto :python_found
)

python3 --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python3"
    goto :python_found
)

py --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=py"
    goto :python_found
)

:: 检查常见安装路径
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%PROGRAMFILES%\Python312\python.exe"
    "%PROGRAMFILES%\Python311\python.exe"
    "%PROGRAMFILES%\Python310\python.exe"
) do (
    if exist %%P (
        set "PYTHON_CMD=%%~P"
        goto :python_found
    )
)

:: 未找到 Python
echo.
echo %RED%╔══════════════════════════════════════════════════════════════════════╗%RESET%
echo %RED%║  ✗ 未检测到 Python 3.10+，请先安装 Python 后重试                     ║%RESET%
echo %RED%╠══════════════════════════════════════════════════════════════════════╣%RESET%
echo %RED%║                                                                      ║%RESET%
echo %RED%║  下载地址：https://www.python.org/downloads/                         ║%RESET%
echo %RED%║                                                                      ║%RESET%
echo %RED%║  ⚠ 安装时务必勾选 "Add Python to PATH"                               ║%RESET%
echo %RED%║                                                                      ║%RESET%
echo %RED%╚══════════════════════════════════════════════════════════════════════╝%RESET%
echo.
pause
exit /b 1

:python_found
:: 获取 Python 版本
for /f "tokens=2" %%V in ('!PYTHON_CMD! --version 2^>^&1') do set "PYTHON_VERSION=%%V"
echo %GREEN%✓ Python %PYTHON_VERSION% 已安装%RESET%

:: 检查版本是否满足要求 (>= 3.10)
for /f "tokens=1,2 delims=." %%A in ("%PYTHON_VERSION%") do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)
if %PY_MAJOR% LSS 3 (
    echo %RED%✗ Python 版本过低，需要 3.10 或更高版本%RESET%
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo %RED%✗ Python 版本过低，需要 3.10 或更高版本%RESET%
    pause
    exit /b 1
)

:: ============================================================================
:: 克隆项目
:: ============================================================================
echo.
echo %CYAN%[3/6]%RESET% 下载项目...

set "PROJECT_DIR=%CD%\Astrbot-desktop-assistant"

if exist "!PROJECT_DIR!\.git" (
    echo 检测到已有项目，正在更新...
    cd /d "!PROJECT_DIR!"
    git pull
    if !ERRORLEVEL! NEQ 0 (
        echo %YELLOW%⚠ 更新失败，尝试重新克隆...%RESET%
        cd /d "%CD%"
        rmdir /s /q "!PROJECT_DIR!" 2>nul
        goto :clone_project
    )
    echo %GREEN%✓ 项目更新完成%RESET%
    goto :after_clone
)

:clone_project
if exist "!PROJECT_DIR!" (
    rmdir /s /q "!PROJECT_DIR!" 2>nul
)

echo 正在下载项目（使用浅克隆加速）...
echo 下载地址: !CLONE_URL!
echo.

git clone --depth 1 "!CLONE_URL!" "!PROJECT_DIR!"

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo %YELLOW%⚠ 下载失败，尝试直连 GitHub...%RESET%
    git clone --depth 1 "%GITHUB_REPO%" "!PROJECT_DIR!"
    
    if !ERRORLEVEL! NEQ 0 (
        echo %RED%✗ 下载失败，请检查网络连接%RESET%
        pause
        exit /b 1
    )
)

echo %GREEN%✓ 项目下载完成%RESET%

:after_clone
cd /d "!PROJECT_DIR!"

:: 显示版本信息
echo.
echo %CYAN%版本信息：%RESET%
for /f "usebackq tokens=*" %%i in (`git log -1 --format^="%%h %%ci %%s"`) do (
    echo   最新提交: %%i
)

:: ============================================================================
:: 创建虚拟环境并安装依赖
:: ============================================================================
echo.
echo %CYAN%[4/6]%RESET% 配置 Python 环境...

set "VENV_DIR=!PROJECT_DIR!\venv"

if exist "!VENV_DIR!\Scripts\python.exe" (
    echo %GREEN%✓ 虚拟环境已存在%RESET%
) else (
    echo 正在创建虚拟环境...
    "!PYTHON_CMD!" -m venv "!VENV_DIR!"
    if !ERRORLEVEL! NEQ 0 (
        echo %YELLOW%⚠ 创建虚拟环境失败，将使用系统 Python%RESET%
    ) else (
        echo %GREEN%✓ 虚拟环境创建成功%RESET%
    )
)

:: 设置 Python 路径
if exist "!VENV_DIR!\Scripts\python.exe" (
    set "PYTHON_CMD=!VENV_DIR!\Scripts\python.exe"
)

echo.
echo %CYAN%[5/6]%RESET% 安装依赖包（这可能需要几分钟）...

:: 升级 pip
"!PYTHON_CMD!" -m pip install --upgrade pip -q 2>nul

:: 安装依赖
"!PYTHON_CMD!" -m pip install -r "!PROJECT_DIR!\requirements.txt" -q
if !ERRORLEVEL! NEQ 0 (
    echo %YELLOW%⚠ 部分依赖安装失败，尝试逐个安装核心依赖...%RESET%
    
    for %%D in (
        "PySide6>=6.5.0"
        "qasync>=0.27.1"
        "httpx[http2]>=0.24.0"
        "websockets>=11.0.0"
        "Pillow>=9.0.0"
        "mss>=9.0.0"
        "pynput>=1.7.0"
    ) do (
        echo   安装 %%~D...
        "!PYTHON_CMD!" -m pip install %%~D -q 2>nul
    )
)

echo %GREEN%✓ 依赖安装完成%RESET%

:: ============================================================================
:: 自动配置（桌面快捷方式 + 开机自启）
:: ============================================================================
echo.
echo %CYAN%[6/6]%RESET% 自动配置...

:: 创建桌面快捷方式
set "SHORTCUT_VBS=%TEMP%\create_shortcut.vbs"
set "DESKTOP=%USERPROFILE%\Desktop"

:: 使用虚拟环境的 pythonw.exe
if exist "!VENV_DIR!\Scripts\pythonw.exe" (
    set "TARGET_SCRIPT=!VENV_DIR!\Scripts\pythonw.exe"
    set "ARGUMENTS=-m desktop_client"
) else (
    set "TARGET_SCRIPT=!PROJECT_DIR!\start.bat"
    set "ARGUMENTS="
)

echo Set oWS = WScript.CreateObject^("WScript.Shell"^) > "!SHORTCUT_VBS!"
echo sLinkFile = "!DESKTOP!\AstrBot Desktop Assistant.lnk" >> "!SHORTCUT_VBS!"
echo Set oLink = oWS.CreateShortcut^(sLinkFile^) >> "!SHORTCUT_VBS!"
echo oLink.TargetPath = "!TARGET_SCRIPT!" >> "!SHORTCUT_VBS!"
if not "!ARGUMENTS!"=="" (
    echo oLink.Arguments = "!ARGUMENTS!" >> "!SHORTCUT_VBS!"
)
echo oLink.WorkingDirectory = "!PROJECT_DIR!" >> "!SHORTCUT_VBS!"
echo oLink.Description = "AstrBot Desktop Assistant" >> "!SHORTCUT_VBS!"
echo oLink.Save >> "!SHORTCUT_VBS!"

cscript //nologo "!SHORTCUT_VBS!" 2>nul
del "!SHORTCUT_VBS!" 2>nul

if exist "!DESKTOP!\AstrBot Desktop Assistant.lnk" (
    echo %GREEN%✓ 桌面快捷方式已创建%RESET%
) else (
    echo %YELLOW%⚠ 桌面快捷方式创建失败%RESET%
)

:: 配置开机自启
echo 正在配置开机自启...
"!PYTHON_CMD!" -c "from desktop_client.platforms import get_platform_adapter; adapter = get_platform_adapter(); result = adapter.enable_autostart(); print(result.message if result else '')" 2>nul

if !ERRORLEVEL! EQU 0 (
    echo %GREEN%✓ 开机自启已配置%RESET%
) else (
    echo %YELLOW%⚠ 开机自启配置失败，可稍后在设置中开启%RESET%
)

:: ============================================================================
:: 安装完成
:: ============================================================================
echo.
echo %GREEN%╔══════════════════════════════════════════════════════════════════════╗%RESET%
echo %GREEN%║                                                                      ║%RESET%
echo %GREEN%║                    ✓ 安装成功！                                      ║%RESET%
echo %GREEN%║                                                                      ║%RESET%
echo %GREEN%╠══════════════════════════════════════════════════════════════════════╣%RESET%
echo %GREEN%║                                                                      ║%RESET%
echo %GREEN%║  项目目录: !PROJECT_DIR!      ║%RESET%
echo %GREEN%║                                                                      ║%RESET%
echo %GREEN%║  启动方式:                                                           ║%RESET%
echo %GREEN%║    • 双击桌面快捷方式 "AstrBot Desktop Assistant"                    ║%RESET%
echo %GREEN%║    • 或运行 start.bat                                                ║%RESET%
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
    start "" "!PYTHON_CMD!" -m desktop_client
    echo %GREEN%✓ 应用已启动%RESET%
)

echo.
echo %CYAN%感谢使用 AstrBot Desktop Assistant！%RESET%
echo.
pause