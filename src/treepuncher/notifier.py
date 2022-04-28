import asyncio
import logging
from typing import List, Callable, Optional, TYPE_CHECKING
if TYPE_CHECKING:
	from .treepuncher import Treepuncher

from .addon import Addon

class Provider(Addon):
	async def notify(self, text, log:bool = False, **kwargs):
		raise NotImplementedError

class Notifier:
	_report_functions : List[Callable]
	_providers : List[Provider]
	_client : 'Treepuncher'
	logger : logging.Logger

	def __init__(self, client:'Treepuncher'):
		self._report_functions = []
		self._providers = []
		self._client = client
		self.logger = client.logger.getChild("notifier")
	
	@property
	def providers(self) -> List[Provider]:
		return self._providers

	def add_reporter(self, fn:Callable):
		self._report_functions.append(fn)
		return fn

	def add_provider(self, p:Provider):
		self._providers.append(p)

	def get_provider(self, name:str) -> Optional[Provider]:
		for p in self.providers:
			if p.name == name:
				return p
		return None

	def report(self) -> str:
		return '\n'.join(str(fn()).strip() for fn in self._report_functions)

	async def notify(self, text, log:bool = False, **kwargs):
		self.logger.info("%s %s (%s)", "[n]" if log else "[N]", text, str(kwargs))
		await asyncio.gather(
			*(p.notify(text, log=log, **kwargs) for p in self.providers)
		)

	async def start(self):
		await asyncio.gather(
			*(p.initialize() for p in self.providers)
		)

	async def stop(self):
		await asyncio.gather(
			*(p.cleanup() for p in self.providers)
		)
