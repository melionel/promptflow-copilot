import logging

def get_logger():
    log_file_name = "pfcopilot_err.log"
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    file_handler = logging.FileHandler(log_file_name)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.ERROR)
    
    logger.addHandler(file_handler)

    return logger