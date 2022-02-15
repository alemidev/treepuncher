import re
import logging
import asyncio
import datetime
import uuid

from typing import List, Dict, Tuple, Union, Optional, Any, Type, get_type_hints
from enum import Enum
from dataclasses import dataclass
from configparser import ConfigParser

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiocraft.client import MinecraftClient
from aiocraft.mc.packet import Packet

from .storage import Storage
from .notifier import Notifier
from .game import GameState, GameChat, GameInventory, GameTablist, GameWorld

REMOVE_COLOR_FORMATS = re.compile(r"§[0-9a-z]")

class ConfigObject:
	def __getitem__(self, key:str) -> Any:
		return getattr(self, key)

class Addon:
	name : str
	config : ConfigObject
	_client : 'Treepuncher'

	@dataclass(frozen=True)
	class Options(ConfigObject):
		pass

	@property
	def client(self) -> 'Treepuncher':
		return self._client

	def __init__(self, client:'Treepuncher'):
		self._client = client
		self.name = type(self).__name__
		cfg = self._client.config
		kwargs : Dict[str, Any] = {}
		for name, clazz in get_type_hints(self.Options).items():
			default = getattr(self.Options, name, None)
			if cfg.has_option(self.name, name):
				if clazz is bool:
					kwargs[name] = self._client.config[self.name].getboolean(name)
				else:
					kwargs[name] = clazz(self._client.config[self.name].get(name))
			elif default is None:
				raise ValueError(f"Missing required value '{name}' of type '{clazz.__name__}' in section '{self.name}'")
			else: # not really necessary since it's a dataclass but whatever
				kwargs[name] = default
		self.config = self.Options(**kwargs)

	async def initialize(self):
		pass

	async def cleanup(self):
		pass

class Treepuncher(
		GameState,
		GameChat,
		GameInventory,
		GameTablist,
		GameWorld
):
	name : str
	config : ConfigParser
	storage : Storage

	notifier : Notifier
	scheduler : AsyncIOScheduler
	modules : List[Addon]
	ctx : Dict[Any, Any]

	def __init__(self, name:str, *args, config_file:str=None, **kwargs):
		super().__init__(*args, **kwargs)
		self.ctx = dict()

		self.name = name
		self.config = ConfigParser()
		config_path = config_file or f'config-{self.name}.ini'
		self.config.read(config_path)

		self.storage = Storage(self.name)

		self.modules = []

		# self.notifier = notifier or Notifier()
		tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname() # APScheduler will complain if I don't specify a timezone...
		self.scheduler = AsyncIOScheduler(timezone=tz)
		logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING) # So it's way less spammy
		self.scheduler.start(paused=True)

	@property
	def playerName(self) -> str:
		if self.online_mode:
			if self._authenticator and self._authenticator.selectedProfile:
				return self._authenticator.selectedProfile.name
			raise ValueError("Username unknown: client not authenticated")
		else:
			if self._username:
				return self._username
			raise ValueError("No username configured for offline mode")

	async def start(self):
		await self.notifier.initialize(self)
		for m in self.modules:
			await m.initialize(self)
		await super().start()
		self.scheduler.resume()

	async def stop(self, force:bool=False):
		self.scheduler.pause()
		await super().stop(force=force)
		for m in self.modules:
			await m.cleanup()
		await self.notifier.cleanup(self)

	def install(self, module:Type[Addon]) -> Type[Addon]:
		self.modules.append(module(self))
		return module

	async def write(self, packet:Packet, wait:bool=False):
		await self.dispatcher.write(packet, wait)

