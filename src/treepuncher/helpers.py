import logging

from typing import Dict

from termcolor import colored

def configure_logging(name:str, level=logging.INFO, color:bool = True, path:str = "log"):
	import os
	from logging.handlers import RotatingFileHandler

	class ColorFormatter(logging.Formatter):
		def __init__(self, fmt:str, datefmt:str=None):
			self.fmt : str = fmt
			self.formatters : Dict[int, logging.Formatter] = {
				logging.DEBUG: logging.Formatter(colored(fmt, color='grey'), datefmt),
				logging.INFO: logging.Formatter(colored(fmt), datefmt),
				logging.WARNING: logging.Formatter(colored(fmt, color='yellow'), datefmt),
				logging.ERROR: logging.Formatter(colored(fmt, color='red'), datefmt),
				logging.CRITICAL: logging.Formatter(colored(fmt, color='red', attrs=['bold']), datefmt),
			}
	
		def format(self, record:logging.LogRecord) -> str:
			if record.exc_text: # jank way to color the stacktrace but will do for now
				record.exc_text = colored(record.exc_text, color='grey', attrs=['bold'])
			return self.formatters[record.levelno].format(record)

	logger = logging.getLogger()
	logger.setLevel(level)
	# create file handler which logs even debug messages
	if not os.path.isdir(path):
		os.mkdir(path)
	fh = RotatingFileHandler(f'{path}/{name}.log', maxBytes=1048576, backupCount=5) # 1MB files
	fh.setLevel(logging.DEBUG)
	# create console handler with a higher log level
	ch = logging.StreamHandler()
	ch.setLevel(logging.DEBUG)
	# create formatter and add it to the handlers
	file_formatter = logging.Formatter("[%(asctime)s.%(msecs)03d] [%(name)s] [%(levelname)s] %(message)s", "%b %d %Y %H:%M:%S")
	print_formatter = ColorFormatter("%(asctime)s| %(message)s", "%H:%M:%S") if color else logging.Formatter("> %(message)s")
	fh.setFormatter(file_formatter)
	ch.setFormatter(print_formatter)
	# add the handlers to the logger
	logger.addHandler(fh)
	logger.addHandler(ch)
