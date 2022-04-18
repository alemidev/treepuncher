import re
import json
import logging
import asyncio
import datetime
import uuid

from typing import List, Dict, Optional, Any, Type, get_type_hints
from time import time
from dataclasses import dataclass, MISSING
from configparser import ConfigParser

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiocraft.mc.packet import Packet
from aiocraft.mc.auth import AuthInterface, AuthException, MojangAuthenticator, MicrosoftAuthenticator, OfflineAuthenticator

from .storage import Storage, SystemState
from .notifier import Notifier
from .game import GameState, GameChat, GameInventory, GameTablist, GameWorld

REMOVE_COLOR_FORMATS = re.compile(r"§[0-9a-z]")


class ConfigObject:
	def __getitem__(self, key: str) -> Any:
		return getattr(self, key)


class Addon:
	name: str
	config: ConfigObject
	_client: 'Treepuncher'

	@dataclass(frozen=True)
	class Options(ConfigObject):
		pass

	@property
	def client(self) -> 'Treepuncher':
		return self._client

	def __init__(self, client: 'Treepuncher', *args, **kwargs):
		self._client = client
		self.name = type(self).__name__
		cfg = self._client.config
		opts: Dict[str, Any] = {}
		cfg_clazz = get_type_hints(type(self))['config']
		if cfg_clazz is not ConfigObject:
			for name, field in cfg_clazz.__dataclass_fields__.items():
				default = field.default if field.default is not MISSING \
					else field.default_factory() if field.default_factory is not MISSING \
					else MISSING
				if cfg.has_option(self.name, name):
					if field.type is bool:
						opts[name] = self._client.config[self.name].getboolean(name)
					else:
						opts[name] = field.type(self._client.config[self.name].get(name))
				elif default is MISSING:
					raise ValueError(
						f"Missing required value '{name}' of type '{field.type.__name__}' in section '{self.name}'"
					)
				else:  # not really necessary since it's a dataclass but whatever
					opts[name] = default
		self.config = self.Options(**opts)
		self.register()

	def register(self):
		pass

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
	name: str
	config: ConfigParser
	storage: Storage

	notifier: Notifier
	scheduler: AsyncIOScheduler
	modules: List[Addon]
	ctx: Dict[Any, Any]

	_processing: bool

	def __init__(
		self,
		name: str,
		config_file: str = None,
		online_mode: bool = True,
		legacy: bool = False,
		notifier: Notifier = None,
		**kwargs
	):
		self.ctx = dict()

		self.name = name
		self.config = ConfigParser()
		config_path = config_file or f'{self.name}.ini'
		self.config.read(config_path)

		authenticator : AuthInterface

		def opt(k:str) -> Any:
			return kwargs.get(k) or self.config['Treepuncher'].get(k)

		if not online_mode:
			authenticator = OfflineAuthenticator(self.name)
		elif legacy:
			authenticator = MojangAuthenticator(
				username= opt('username') or name,
				password= opt('password') 
			)
			if opt('legacy_token'):
				authenticator.deserialize(json.loads(opt('mojang_token')))

		else:
			authenticator = MicrosoftAuthenticator(
				client_id= opt('client_id'),
				client_secret= opt('client_secret'),
				redirect_uri= opt('redirect_uri'),
				code= opt('code'),
			)

		self.storage = Storage(self.name)
		prev = self.storage.system()  # if this isn't 1st time, this won't be None. Load token from there
		if prev:
			if self.name != prev.name:
				self.logger.warning("Saved credentials belong to another session")
			authenticator.deserialize(json.loads(prev.token))
			self.logger.info("Loaded credentials")

		self.modules = []

		self.notifier = notifier or Notifier()
		# tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()  # This doesn't work anymore
		self.scheduler = AsyncIOScheduler()  # TODO APScheduler warns about timezone ugghh
		logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)  # So it's way less spammy
		self.scheduler.start(paused=True)

		super().__init__(opt('server'), online_mode=online_mode, authenticator=authenticator)


	@property
	def playerName(self) -> str:
		return self.authenticator.selectedProfile.name

	async def authenticate(self):
		await super().authenticate()
		state = SystemState(
			name=self.name,
			token=json.dumps(self._authenticator.serialize()),
			start_time=int(time())
		)
		self.storage._set_state(state)

	async def start(self):
		# if self.started: # TODO readd check
		# 	return
		await super().start()
		await self.notifier.initialize()
		for m in self.modules:
			await m.initialize()
		self._processing = True
		self._worker = asyncio.get_event_loop().create_task(self._work())
		self.scheduler.resume()
		self.logger.info("Treepuncher started")

	async def stop(self, force: bool = False):
		self._processing = False
		self.scheduler.pause()
		if self.dispatcher.connected:
			await self.dispatcher.disconnect(block=not force)
		if not force:
			await self._worker
			await self.join_callbacks()
		for m in self.modules:
			await m.cleanup()
		await self.notifier.cleanup()
		await super().stop()
		self.logger.info("Treepuncher stopped")

	def install(self, module: Type[Addon]) -> Type[Addon]:
		self.modules.append(module(self))
		return module

	async def _work(self):
		try:
			server_data = await self.info(host=self.host, port=self.port)
		except Exception:
			return self.logger.exception("exception while pinging server")
		while self._processing:
			try:
				await self.join(
					host=self.host,
					port=self.port,
					proto=server_data['version']['protocol'],
					packet_whitelist=self.callback_keys(filter=Packet),
				)
			except ConnectionRefusedError:
				self.logger.error("Server rejected connection")
			except OSError as e:
				self.logger.error("Connection error : %s", str(e))
			except Exception:
				self.logger.exception("Unhandled exception")
				break
			await asyncio.sleep(5)  # TODO setting
		if self._processing:
			await self.stop(force=True)
