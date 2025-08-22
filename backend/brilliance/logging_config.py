"""
Logging configuration for Brilliance - designed for production safety.
No file logging by default to prevent log accumulation.
"""
import os
import logging
import sys
from typing import Optional


def configure_logging(
    level: Optional[str] = None,
    enable_file_logging: bool = False,
    log_file: str = "app.log"
) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_file_logging: Whether to log to files (disabled by default for production safety)
        log_file: Log file name if file logging is enabled
    
    Returns:
        Configured logger instance
    """
    # Default to WARNING in production to minimize output
    if level is None:
        level = os.getenv("LOG_LEVEL", "WARNING" if os.getenv("FLASK_ENV") == "production" else "INFO")
    
    # Create logger
    logger = logging.getLogger("brilliance")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Console handler (always enabled but minimal in production)
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler (disabled by default for security)
    if enable_file_logging and os.getenv("ENABLE_FILE_LOGGING") == "1":
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(console_format)
        logger.addHandler(file_handler)
        logger.warning(f"File logging enabled: {log_file}")
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


def get_logger() -> logging.Logger:
    """Get the configured logger instance."""
    return logging.getLogger("brilliance")


def safe_print(message: str, level: str = "info") -> None:
    """
    Safe print function that respects logging configuration.
    Use this instead of print() for production code.
    """
    logger = get_logger()
    
    # If logger not configured, configure with minimal settings
    if not logger.handlers:
        configure_logging()
        logger = get_logger()
    
    # Map level to logger method
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message)


# Configure logging on import
configure_logging()
