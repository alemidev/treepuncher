from typing import Callable, List

class Notifier:
	_report_functions : List[Callable]

	def __init__(self):
		self._report_functions = []

	def register(self, fn:Callable):
		self._report_functions.append(fn)
		return fn

	def report(self) -> str:
		return '\n'.join(str(fn()).strip() for fn in self._report_functions)

	def notify(self, text, critical:bool = False, **kwargs):
		print(text)

	async def initialize(self, _client:'Treepuncher'):
		pass

	async def cleanup(self, _client:'Treepuncher'):
		pass

