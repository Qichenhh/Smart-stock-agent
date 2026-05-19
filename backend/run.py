"""启动脚本

注意：需要用环境变量 PYTHONIOENCODING=utf-8 启动，否则Windows GBK编码会报错
示例：PYTHONIOENCODING=utf-8 python run.py
"""

import sys
import io

# 尽力设置UTF-8（对于已初始化的进程可能无效，需要使用 PYTHONIOENCODING 环境变量）
if hasattr(sys.stdout, 'buffer'):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

import uvicorn
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()

    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower()
    )
