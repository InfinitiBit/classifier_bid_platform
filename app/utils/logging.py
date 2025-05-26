import logging
import sys
from pathlib import Path
from loguru import logger
from app.config import LOG_LEVEL, LOG_FILE

def setup_logging():
    """Setup logging configuration"""
    # Create log directory if it doesn't exist
    log_file = Path(LOG_FILE)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure loguru
    config = {
        "handlers": [
            {"sink": sys.stdout, "level": LOG_LEVEL},
            {"sink": LOG_FILE, "rotation": "500 MB", "retention": "10 days", "level": LOG_LEVEL}
        ]
    }
    
    logger.configure(**config)
    return logger

def get_logger(name: str = __name__):
    """Get a logger instance"""
    return logger.bind(name=name)
