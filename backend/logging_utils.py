#!/usr/bin/env python3
"""
Enhanced logging utilities for Crowdworks Monitor
Provides comprehensive logging for backend, frontend, and GUI components
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

class CrowdworksLogger:
    """Enhanced logger for Crowdworks Monitor application"""
    
    def __init__(self, name: str, log_file: Optional[str] = None):
        self.name = name
        self.logger = logging.getLogger(name)
        
        # Create logs directory
        self.log_dir = self._get_log_directory()
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Setup log file
        if log_file:
            self.log_file = os.path.join(self.log_dir, log_file)
        else:
            self.log_file = os.path.join(self.log_dir, f"{name.lower().replace('.', '_')}.log")
        
        self._setup_logger()
    
    def _get_log_directory(self) -> str:
        """Get the logs directory path"""
        if getattr(sys, 'frozen', False):
            # Running as executable
            base_dir = Path(sys.executable).parent.parent
        else:
            # Running as script
            base_dir = Path(__file__).parent.parent
        
        return os.path.join(base_dir, 'logs')
    
    def _setup_logger(self):
        """Setup the logger with file and console handlers"""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Setup file handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        
        # Setup console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        """Log error message"""
        if exc_info:
            import traceback
            self.logger.error(f"{message}\n{traceback.format_exc()}")
        else:
            self.logger.error(message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(message)
    
    def log_status_change(self, component: str, old_status: str, new_status: str, details: str = ""):
        """Log status changes with structured format"""
        timestamp = datetime.now().isoformat()
        message = f"STATUS_CHANGE - {component}: {old_status} -> {new_status}"
        if details:
            message += f" | {details}"
        
        self.info(message)
        
        # Also write to a dedicated status log
        status_log_file = os.path.join(self.log_dir, 'status_changes.log')
        try:
            with open(status_log_file, 'a', encoding='utf-8') as f:
                f.write(f"{timestamp} - {component} - {old_status} -> {new_status} - {details}\n")
        except Exception:
            pass
    
    def log_error_with_context(self, error: Exception, context: str = ""):
        """Log error with additional context"""
        error_msg = f"ERROR - {context}: {str(error)}" if context else f"ERROR: {str(error)}"
        self.error(error_msg)
        
        # Also write to error log
        error_log_file = os.path.join(self.log_dir, 'errors.log')
        try:
            with open(error_log_file, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()} - {context} - {str(error)}\n")
        except Exception:
            pass

# Global logger instances
bot_logger = CrowdworksLogger('bot_service', 'bot_service.log')
api_logger = CrowdworksLogger('api_server', 'api_server.log')
gui_logger = CrowdworksLogger('gui_launcher', 'gui_launcher.log')
scraper_logger = CrowdworksLogger('scraper', 'scraper.log')

def get_logger(name: str) -> CrowdworksLogger:
    """Get a logger instance by name"""
    return CrowdworksLogger(name)


