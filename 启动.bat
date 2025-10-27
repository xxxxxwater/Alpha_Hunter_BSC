@echo off
REM 设置UTF-8编码
chcp 65001 >nul 2>&1
if errorlevel 1 (
    echo Warning: Unable to set UTF-8 encoding
)

title Alpha Hunter - LI.FI版

:MENU
cls
echo.
echo ============================================================
echo              Alpha Hunter - LI.FI版 v1.1.0
echo              智能交易机器人
echo ============================================================
echo.
echo 请选择功能:
echo.
echo   1. 启动交易程序
echo   2. 测试RPC连接
echo   3. 查看日志文件
echo   4. 查看持仓记录
echo   5. 退出
echo.
echo ============================================================
echo.

set /p choice="请输入选项 (1-5): "

if "%choice%"=="1" goto START_TRADE
if "%choice%"=="2" goto TEST_RPC
if "%choice%"=="3" goto VIEW_LOG
if "%choice%"=="4" goto VIEW_POSITIONS
if "%choice%"=="5" goto EXIT

echo.
echo [错误] 无效的选项，请重新选择
pause
goto MENU

:START_TRADE
cls
echo.
echo ============================================================
echo              Alpha Hunter - 启动交易程序
echo ============================================================
echo.
echo [提示] 按 Ctrl+C 可以随时停止程序
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.7+
    echo.
    pause
    goto MENU
)

REM 检查配置文件
if not exist ".env" (
    echo [警告] 未找到配置文件 .env
    echo.
    echo 请先创建配置文件:
    echo   1. 复制 env_example.txt 为 .env
    echo   2. 编辑 .env 文件填入你的私钥和配置
    echo.
    pause
    goto MENU
)

python auto_trade_lifi.py

echo.
echo [完成] 程序已退出
pause
goto MENU

:TEST_RPC
cls
echo.
echo ============================================================
echo              BSC RPC 连接测试工具
echo ============================================================
echo.
echo 正在测试所有RPC节点的连接状态...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.7+
    echo.
    pause
    goto MENU
)

python test_rpc_connection.py

echo.
pause
goto MENU

:VIEW_LOG
cls
echo.
echo ============================================================
echo              查看日志文件
echo ============================================================
echo.

if not exist "alpha_hunter.log" (
    echo [提示] 日志文件不存在，程序尚未运行过
    echo.
    pause
    goto MENU
)

echo 显示最后50行日志:
echo ------------------------------------------------------------
type alpha_hunter.log | more +50
echo ------------------------------------------------------------
echo.
echo 完整日志文件位置: alpha_hunter.log
echo 可以使用文本编辑器打开查看完整内容
echo.
pause
goto MENU

:VIEW_POSITIONS
cls
echo.
echo ============================================================
echo              查看持仓记录
echo ============================================================
echo.

if not exist "positions.json" (
    echo [提示] 持仓文件不存在，当前无持仓
    echo.
    pause
    goto MENU
)

echo 当前持仓信息:
echo ------------------------------------------------------------
type positions.json
echo ------------------------------------------------------------
echo.
pause
goto MENU

:EXIT
cls
echo.
echo ============================================================
echo              感谢使用 Alpha Hunter
echo              祝你交易顺利！🚀
echo ============================================================
echo.
timeout /t 2 >nul
exit


