import logging
logger = logging.getLogger(__name__)

LOG_INFO = "info"
LOG_ERROR = "error"
LOG_DEBUG = "debug"

def log(message, log_level=LOG_INFO):
    log_level = LOG_INFO.lower()
    if log_level == "INFO":
        log_level = LOG_INFO
    logger.log(level=log_level, msg=message)

def log_debug(message):
    logger.debug(message)
    pass

def log_error(message):
    logger.error(message)
