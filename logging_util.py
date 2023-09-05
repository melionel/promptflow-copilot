import logging
import os

pf_logger = None

def get_logger():
    global pf_logger
    if pf_logger is None:
        script_directory = os.path.dirname(os.path.abspath(__file__))
        log_file_name = "pfcopilot.log"
        pf_logger = logging.getLogger('pfcopilot')
        pf_logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler(os.path.join(script_directory, log_file_name))
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        pf_logger.addHandler(file_handler)

    return pf_logger