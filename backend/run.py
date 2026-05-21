"""启动脚本

用法:
    python run.py              # 正常启动
    python run.py --kill       # 杀死占端口进程后启动
    PYTHONIOENCODING=utf-8 python run.py  # Windows 推荐（避免GBK编码错误）
"""

import sys
import io

# 设置 UTF-8 编码
if hasattr(sys.stdout, 'buffer'):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

import uvicorn
from app.config import get_settings


def kill_port(port: int):
    """杀死占用指定端口的进程"""
    import time
    # 用 netstat 找到 PID，用 taskkill 杀掉
    import subprocess as sp
    try:
        # 1. 找 PID
        r = sp.run(f'netstat -ano | findstr :{port} | findstr LISTENING',
                   shell=True, capture_output=True, text=True, timeout=10)
        for line in r.stdout.strip().split('\n'):
            parts = line.strip().split()
            if len(parts) >= 5:
                pid = parts[-1]
                print(f"  找到 PID: {pid}，正在终止...")
                sp.run(f'taskkill /F /PID {pid}', shell=True,
                       capture_output=True, timeout=10)
        time.sleep(2)
        print(f"[OK] 端口 {port} 已释放")
    except Exception as e:
        print(f"[WARN] 端口清理失败: {e}")


if __name__ == "__main__":
    settings = get_settings()

    # 自动处理端口冲突
    if "--kill" in sys.argv:
        kill_port(settings.port)

    print(f"\n启动服务器: http://{settings.host}:{settings.port}")
    print(f"API 文档: http://localhost:{settings.port}/docs\n")

    try:
        uvicorn.run(
            "app.api.main:app",
            host=settings.host,
            port=settings.port,
            reload=False,
            log_level=settings.log_level.lower()
        )
    except OSError as e:
        if "10048" in str(e) or "bind" in str(e).lower():
            print(f"\n[ERROR] 端口 {settings.port} 被占用！")
            print(f"解决方法: python run.py --kill")
            sys.exit(1)
        raise
