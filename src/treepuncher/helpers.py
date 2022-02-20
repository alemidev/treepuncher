import logging

from typing import Dict

from termcolor import colored

def configure_logging(name:str, level=logging.INFO, color:bool = True):
	import os
	from logging.handlers import RotatingFileHandler

	if not os.path.isdir("debug"):
		os.mkdir("debug")

	class ColorFormatter(logging.Formatter):
		def __init__(self, fmt:str):
			self.fmt : str = fmt
			self.formatters : Dict[int, logging.Formatter] = {
				logging.DEBUG: logging.Formatter(colored(fmt, color='grey')),
				logging.INFO: logging.Formatter(colored(fmt)),
				logging.WARNING: logging.Formatter(colored(fmt, color='yellow')),
				logging.ERROR: logging.Formatter(colored(fmt, color='red')),
				logging.CRITICAL: logging.Formatter(colored(fmt, color='red', attrs=['bold'])),
			}
	
		def format(self, record:logging.LogRecord) -> str:
			if record.exc_text: # jank way to color the stacktrace but will do for now
				record.exc_text = colored(record.exc_text, color='grey', attrs=['bold'])
			return self.formatters[record.levelno].format(record)

	logger = logging.getLogger()
	logger.setLevel(level)
	# create file handler which logs even debug messages
	fh = RotatingFileHandler(f'data/{name}.log', maxBytes=1048576, backupCount=5) # 1MB files
	fh.setLevel(logging.DEBUG)
	# create console handler with a higher log level
	ch = logging.StreamHandler()
	ch.setLevel(logging.DEBUG)
	# create formatter and add it to the handlers
	file_formatter = logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s", "%b %d %Y %H:%M:%S")
	print_formatter : logging.Formatter
	if color:
		print_formatter = ColorFormatter("> %(message)s")
	else:
		print_formatter = logging.Formatter("> %(message)s")
	fh.setFormatter(file_formatter)
	ch.setFormatter(print_formatter)
	# add the handlers to the logger
	logger.addHandler(fh)
	logger.addHandler(ch)
