@echo off
REM 清理指定端口的占用进程 (Windows)
if "%1"=="" (
    echo 用法: kill_port.cmd 8000
    exit /b 1
)
echo 正在查找端口 %1 的占用进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%1 " ^| findstr LISTENING') do (
    echo 杀死 PID: %%a
    taskkill /F /PID %%a 2>nul
)
echo 端口 %1 已释放
