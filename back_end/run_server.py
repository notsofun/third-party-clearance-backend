#!/usr/bin/env python
"""
专门用于启动应用的脚本，确保日志配置正确
"""
import uvicorn
import os
import sys
from pathlib import Path

# 确保可以导入项目模块
root_dir = Path(__file__).resolve().parent
project_root = root_dir.parent
sys.path.append(str(root_dir))
sys.path.append(str(project_root))

# 导入日志配置
from log_config import configure_logging

if __name__ == "__main__":
    # 配置日志系统
    configure_logging()
    
    # 启动uvicorn服务器
    uvicorn.run(
        "back_end.server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        # 关闭uvicorn的默认日志配置，使用我们自己的
        log_config=None,
    )