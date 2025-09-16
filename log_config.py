import logging
import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging():
    """配置全局日志系统"""
    
    # 直接在函数内计算项目根目录
    project_root = Path(__file__).resolve().parent
    
    # 确保日志目录存在 - 使用绝对路径确保位置正确
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss")

    # 服务器实例日志文件路径
    server_log_file = log_dir / f"server_{timestamp}.log"
    server_error_log_file = log_dir / f"server_error_{timestamp}.log"
    
    # 获取根logger
    root_logger = logging.getLogger()
    
    # 清除已有的处理器，避免Uvicorn的干扰
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    # 设置日志级别
    root_logger.setLevel(logging.INFO)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 主日志文件处理器
    file_handler = RotatingFileHandler(
        filename=str(server_log_file),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # 错误日志文件处理器
    # error_file_handler = RotatingFileHandler(
    #     filename=str(server_error_log_file),
    #     maxBytes=10*1024*1024,
    #     backupCount=5,
    #     encoding='utf8'
    # )
    # error_file_handler.setFormatter(formatter)
    # error_file_handler.setLevel(logging.ERROR)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # 添加处理器
    root_logger.addHandler(file_handler)
    # root_logger.addHandler(error_file_handler)
    root_logger.addHandler(console_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("msal").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    
    # 记录一条启动日志
    root_logger.info(f"服务器日志系统初始化完成，日志文件: {server_log_file}")
    
    return root_logger

def get_logger(name):
    """获取指定名称的logger"""
    return logging.getLogger(name)