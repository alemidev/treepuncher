import re
import json
import logging
import asyncio
import datetime
import uuid

from typing import List, Dict, Optional, Any, Type, get_args, get_origin, get_type_hints, Set
from time import time
from dataclasses import dataclass, MISSING, fields
from configparser import ConfigParser

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiocraft.mc.packet import Packet
from aiocraft.mc.auth import AuthInterface, AuthException, MojangAuthenticator, MicrosoftAuthenticator, OfflineAuthenticator

from .storage import Storage, SystemState
from .notifier import Notifier
from .addon import Addon
from .game import GameState, GameChat, GameInventory, GameTablist, GameWorld

class MissingParameterError(Exception):
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

	notifier: Optional[Notifier]
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
		**kwargs
	):
		self.ctx = dict()

		self.name = name
		self.config = ConfigParser()
		config_path = config_file or f'{self.name}.ini'
		self.config.read(config_path)

		authenticator : AuthInterface

		def opt(k:str, required=False, default=None) -> Any:
			v = kwargs.get(k) or self.config['Treepuncher'].get(k) or default
			if not v and required:
				raise MissingParameterError(f"Missing configuration parameter '{k}'")
			return v

		if not online_mode:
			authenticator = OfflineAuthenticator(self.name)
		elif legacy:
			authenticator = MojangAuthenticator(
				username= opt('username', default=name, required=True),
				password= opt('password') 
			)
			if opt('legacy_token'):
				authenticator.deserialize(json.loads(opt('legacy_token')))
		else:
			authenticator = MicrosoftAuthenticator(
				client_id= opt('client_id', required=True),
				client_secret= opt('client_secret', required=True),
				redirect_uri= opt('redirect_uri', required=True),
				code= opt('code'),
			)

		self.storage = Storage(self.name)

		self.modules = []
		self.notifier = None

		# tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()  # This doesn't work anymore
		self.scheduler = AsyncIOScheduler()  # TODO APScheduler warns about timezone ugghh
		logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)  # So it's way less spammy
		self.scheduler.start(paused=True)

		super().__init__(opt('server', required=True), online_mode=online_mode, authenticator=authenticator)

		prev = self.storage.system()  # if this isn't 1st time, this won't be None. Load token from there
		if prev:
			if self.name != prev.name:
				self.logger.warning("Saved session belong to another user")
			authenticator.deserialize(json.loads(prev.token))
			self.logger.info("Loaded authenticated session")


	@property
	def playerName(self) -> str:
		return self.authenticator.selectedProfile.name

	async def authenticate(self):
		await super().authenticate()
		state = SystemState(
			name=self.name,
			token=json.dumps(self.authenticator.serialize()),
			start_time=int(time())
		)
		self.storage._set_state(state)

	async def start(self):
		# if self.started: # TODO readd check
		# 	return
		await super().start()
		if not self.notifier:
			self.notifier = Notifier()
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
		if self.notifier:
			await self.notifier.cleanup()
		await super().stop()
		self.logger.info("Treepuncher stopped")

	def install(self, module: Type[Addon]) -> Type[Addon]:
		m = module(self)
		self.modules.append(m)
		if isinstance(m, Notifier):
			if self.notifier:
				self.logger.warning("Replacing previously loaded notifier %s", str(self.notifier))
			self.notifier = m
		return module

	async def _work(self):
		try:
			server_data = await self.info()
			self.dispatcher.set_proto(server_data['version']['protocol'])
		except Exception:
			return self.logger.exception("exception while pinging server")
		while self._processing:
			try:
				self.dispatcher.whitelist(self.callback_keys(filter=Packet))
				await self.join()
			except ConnectionRefusedError:
				self.logger.error("Server rejected connection")
			except OSError as e:
				self.logger.error("Connection error : %s", str(e))
			except AuthException as e:
				self.logger.error("Auth exception : [%s|%d] %s (%s)", e.endpoint, e.code, e.data, e.kwargs)
				break
			except Exception:
				self.logger.exception("Unhandled exception")
				break
			if self._processing:
				await asyncio.sleep(self.config['core'].getfloat('reconnect_delay', fallback=5))
		if self._processing:
			await self.stop(force=True)
