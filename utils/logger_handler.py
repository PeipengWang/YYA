import logging
import os
from logging.handlers import TimedRotatingFileHandler
from utils.path_tool import get_abs_path

# 日志根目录
LOG_ROOT = get_abs_path("logs")
os.makedirs(LOG_ROOT, exist_ok=True)

# 日志格式
DEFAULT_LOG_FORMAT = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

def get_logger(
        name: str = "agent",
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        log_file=None,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 防止重复添加handler，避免日志重复打印
    if logger.handlers:
        return logger

    # 1.控制台输出handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)
    logger.addHandler(console_handler)

    # 2.文件输出handler：按天切割日志，保留7天
    if log_file is None:
        log_file = f"{name}.log"
    log_full_path = os.path.join(LOG_ROOT, log_file)

    file_handler = TimedRotatingFileHandler(
        filename=log_full_path,
        when="midnight",    # 每日凌晨切分
        interval=1,
        backupCount=7,      # 保留7天日志
        encoding="utf-8"
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)
    logger.addHandler(file_handler)

    # 禁止日志向上传播到root logger
    logger.propagate = False
    return logger


logger = get_logger()
# 测试入口
if __name__ == '__main__':
    log = get_logger("test")
    log.debug("调试日志，只写入文件")
    log.info("普通信息，控制台+文件都输出")
    log.warning("警告日志")
    log.error("错误日志")