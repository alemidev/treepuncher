import json
import logging
import asyncio
import datetime
import pkg_resources

from typing import Coroutine, List, Dict, Optional, Union, Any, Type, get_args, get_origin, get_type_hints, Set, Callable
from time import time
from dataclasses import dataclass, MISSING, fields
from configparser import ConfigParser, SectionProxy

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiocraft.mc.packet import Packet
from aiocraft.mc.auth import AuthInterface, AuthException, MojangAuthenticator, MicrosoftAuthenticator, OfflineAuthenticator

from .storage import Storage, SystemState, AuthenticatorState
from .game import GameState, GameChat, GameInventory, GameTablist, GameWorld
from .scaffold import ConfigObject
from .addon import Addon
from .notifier import Notifier, Provider, LoggingProvider

__VERSION__ = pkg_resources.get_distribution('treepuncher').version


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

		self.notifier = Notifier(self)

		self.modules = []

		# tz = datetime.datetime.now(datetime.timezone.utc).astimezone().tzname()  # This doesn't work anymore
		self.scheduler = AsyncIOScheduler()  # TODO APScheduler warns about timezone ugghh
		logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)  # So it's way less spammy
		self.scheduler.start(paused=True)

		super().__init__(opt('server', required=True), online_mode=online_mode, authenticator=authenticator)

		prev = self.storage.system()  # if this isn't 1st time, this won't be None. Load token from there
		state = SystemState(self.name, __VERSION__, 0)
		if prev:
			state.start_time = prev.start_time
			if self.name != prev.name:
				self.logger.warning("Saved session belong to another user")
			if prev.version != state.version:
				self.logger.warning("Saved session uses a different version")
			prev_auth = self.storage.auth()
			if prev_auth:
				if prev_auth.legacy ^ isinstance(authenticator, MicrosoftAuthenticator):
					self.logger.warning("Saved session is incompatible with configured authenticator")
				authenticator.deserialize(prev_auth.token)
				self.logger.info("Loaded session from %s", prev_auth.date)
		self.storage._set_state(state)

	@property
	def cfg(self) -> SectionProxy:
		return self.config["Treepuncher"]

	@property
	def playerName(self) -> str:
		return self.authenticator.selectedProfile.name

	async def authenticate(self):
		await super().authenticate()
		state = AuthenticatorState(
			date=datetime.datetime.now(),
			token=self.authenticator.serialize(),
			legacy=isinstance(self.authenticator, MojangAuthenticator)
		)
		self.storage._set_auth(state)

	async def start(self):
		# if self.started: # TODO readd check
		# 	return
		await super().start()

		await self.notifier.start()
		await asyncio.gather(
			*(m.initialize() for m in self.modules)
		)
		self._processing = True
		self._worker = asyncio.get_event_loop().create_task(self._work())
		self.scheduler.resume()
		self.logger.info("Treepuncher started")
		self.storage._set_state(SystemState(self.name, __VERSION__, time()))

	async def stop(self, force: bool = False):
		self._processing = False
		self.scheduler.pause()
		if self.dispatcher.connected:
			await self.dispatcher.disconnect(block=not force)
		if not force:
			await self._worker
			await self.join_callbacks()
			await asyncio.gather(
				*(m.cleanup() for m in self.modules)
			)
		await super().stop()
		self.logger.info("Treepuncher stopped")

	def install(self, module: Type[Addon]) -> Type[Addon]:
		m = module(self)
		if isinstance(m, Provider):
			self.notifier.add_provider(m)
		elif isinstance(m, Addon):
			self.modules.append(m)
		else:
			raise ValueError("Given type is not an addon")
		return module

	async def _work(self):
		try:
			if "force_proto" in self.cfg:
				self.dispatcher.set_proto(self.cfg.getint('force_proto'))
			else:
				try:
					server_data = await self.info()
					if "version" in server_data and "protocol" in server_data["version"]:
						self.dispatcher.set_proto(server_data['version']['protocol'])
				except OSError as e:
					self.logger.error("Connection error : %s", str(e))

			self.dispatcher.whitelist(self.callback_keys(filter=Packet))
			self.dispatcher.log_ignored_packets(self.cfg.getboolean('log_ignored_packets', fallback=False))

			while self._processing:
				try:
					await self.join()
				except OSError as e:
					self.logger.error("Connection error : %s", str(e))
				except AuthException as e:
					self.logger.error("Auth exception : [%s|%d] %s (%s)", e.endpoint, e.code, e.data, e.kwargs)
					break

				if self._processing: # don't sleep if Treepuncher is stopping
					await asyncio.sleep(self.cfg.getfloat('reconnect_delay', fallback=5))

		except Exception:
			self.logger.exception("Unhandled exception")

		if self._processing:
			await self.stop(force=True)
