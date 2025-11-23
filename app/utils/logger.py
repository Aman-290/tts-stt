"""Simple logging utility for Jarvis (with JSON file logging)"""
import logging
import json
import os
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """Formats logs as JSON objects"""
    def format(self, record):
        log_record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage()
        }
        return json.dumps(log_record, ensure_ascii=False)


def get_logger(name: str = "jarvis") -> logging.Logger:
    """Get a configured logger instance (backward compatible)"""
    logger = logging.getLogger(name)

    # Prevent duplicates if already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # ---------------------
    # 1. Console Handler (OLD BEHAVIOR)
    # ---------------------
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # ---------------------
    # 2. JSON File Handler (NEW BEHAVIOR)
    # ---------------------
    log_file = "jarvis_logs.json"

    # If file does not exist, create it
    if not os.path.exists(log_file):
        with open(log_file, "w", encoding="utf-8") as f:
            pass  # create empty file

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    json_formatter = JsonFormatter()
    file_handler.setFormatter(json_formatter)

    logger.addHandler(file_handler)

    return logger
