from typing import Callable, List

from .addon import Addon

class Notifier(Addon): # TODO this should be an Addon too!
	_report_functions : List[Callable]

	def __init__(self):
		self._report_functions = []

	def add_reporter(self, fn:Callable):
		self._report_functions.append(fn)
		return fn

	def report(self) -> str:
		return '\n'.join(str(fn()).strip() for fn in self._report_functions)

	def notify(self, text, log:bool = False, **kwargs):
		print(text)

	async def initialize(self):
		pass

	async def cleanup(self):
		pass

