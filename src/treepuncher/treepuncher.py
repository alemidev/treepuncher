import json
import logging
import asyncio
import datetime
import pkg_resources

from typing import Any, Type
from time import time
from configparser import ConfigParser

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiocraft.packet import Packet
from aiocraft.auth import AuthInterface, AuthException, MojangAuthenticator, MicrosoftAuthenticator, OfflineAuthenticator
from aiocraft.auth.microsoft import InvalidStateError

from .storage import StorageDriver, SystemState, AuthenticatorState
from .game import GameState, GameChat, GameInventory, GameTablist, GameWorld, GameContainer
from .addon import Addon
from .notifier import Notifier, Provider

__VERSION__ = pkg_resources.get_distribution('treepuncher').version

async def _cleanup(m: Addon, l: logging.Logger):
	await m.cleanup()
	l.debug("Cleaned up addon %s", m.name)

class MissingParameterError(Exception):
	pass

class Treepuncher(
	GameState,
	GameChat,
	GameInventory,
	GameContainer,
	GameTablist,
	GameWorld,
	# GameMovement
):
	name: str
	storage: StorageDriver

	notifier: Notifier
	scheduler: AsyncIOScheduler
	modules: list[Addon]
	ctx: dict[Any, Any]

	_processing: bool
	_proto_override: int
	_host: str
	_port: int

	def __init__(
		self,
		name: str,
		config_file: str = "",
		**kwargs
	):
		self.ctx = dict()

		self.name = name
		self.config = ConfigParser()
		self.config.read(config_file or f"{self.name}.ini")  # TODO wrap with pathlib

		authenticator : AuthInterface

		def opt(k, required=False, default=None, t=str):
			v = kwargs.get(k)
			if v is None:
				v = self.cfg.get(k)
			if v is None:
				v = default
			if not v and required:
				raise MissingParameterError(f"Missing configuration parameter '{k}'")
			if t is bool and isinstance(v, str) and v.lower().strip() == 'false': # hardcoded special case
				return False
			if v is None:
				return None
			return t(v)

		if not opt('online_mode', default=True, t=bool):
			authenticator = OfflineAuthenticator(self.name)
		elif opt('legacy', default=False, t=bool):
			authenticator = MojangAuthenticator(
				username= opt('username', default=name, required=True),
				password= opt('password'),
				session_server_override= opt('session_server_override'),
				auth_server_override= opt('auth_server_override'),
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

		super().__init__(
			authenticator=authenticator,
			online_mode=opt('online_mode', default=True, t=bool),
		)

		self._proto_override = opt('force_proto', t=int)
		self._host = opt('server', required=True)
		if ":" in self._host:
			h, p = self._host.split(":", 1)
			self._host = h
			self._port = int(p)
		else:
			self._host, self._port = self.resolve_srv(self._host)

		self.storage = StorageDriver(opt('session_file') or f"data/{name}.session")  # TODO wrap with pathlib

		self.notifier = Notifier(self)

		self.modules = []

		self.scheduler = AsyncIOScheduler()
		logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)  # So it's way less spammy
		self.scheduler.start(paused=True)

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
				if prev_auth.legacy ^ isinstance(authenticator, MojangAuthenticator):
					self.logger.warning("Saved session is incompatible with configured authenticator")
				authenticator.deserialize(prev_auth.token)
				self.logger.info("Loaded session from %s", prev_auth.date)
		self.storage._set_state(state)

	@property
	def playerName(self) -> str:
		return self.authenticator.selectedProfile.name

	async def authenticate(self):
		sleep_interval = self.cfg.getfloat("auth_retry_interval", fallback=60.0)
		for _ in range(self.cfg.getint("auth_retry_count", fallback=5)):
			try:
				await super().authenticate()
				state = AuthenticatorState(
					date=datetime.datetime.now(),
					token=self.authenticator.serialize(),
					legacy=isinstance(self.authenticator, MojangAuthenticator)
				)
				self.storage._set_auth(state)
				return
			except AuthException as e:
				if e.data["error"] == "request timed out":
					await asyncio.sleep(sleep_interval)
					continue
				raise e  # retrying won't help anyway

	async def start(self):
		# if self.started: # TODO readd check
		# 	return
		await super().start()

		await self.notifier.start()
		self.logger.debug("Notifier started")
		await asyncio.gather(
			*(m.initialize() for m in self.modules)
		)
		self.logger.debug("Addons initialized")
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
			self.logger.debug("Joined worker")
			await self.join_callbacks()
			self.logger.debug("Joined callbacks")
			await asyncio.gather(
				*(_cleanup(m, self.logger) for m in self.modules)
			)
			self.logger.debug("Cleaned up addons")
			await self.notifier.stop()
			self.logger.debug("Notifier stopped")
		await super().stop()
		self.logger.info("Treepuncher stopped")

	def install(self, module: Type[Addon]) -> Addon:
		m = module(self)
		if isinstance(m, Provider):
			self.notifier.add_provider(m)
		elif isinstance(m, Addon):
			self.modules.append(m)
		else:
			raise ValueError("Given type is not an addon")
		return m

	async def _work(self):
		self.logger.debug("Worker started")
		try:
			log_ignored_packets = self.cfg.getboolean('log_ignored_packets', fallback=False)
			whitelist = self.callback_keys(filter=Packet)
			if self._proto_override:
				proto = self._proto_override
			else:
				try:
					server_data = await self.info(self._host, self._port, whitelist=whitelist, log_ignored_packets=log_ignored_packets)
					if "version" in server_data and "protocol" in server_data["version"]:
						proto = server_data['version']['protocol']
				except OSError as e:
					self.logger.error("Connection error : %s", str(e))

			while self._processing:
				try:
					await self.join(self._host, self._port, proto, whitelist=whitelist, log_ignored_packets=log_ignored_packets)
				except OSError as e:
					self.logger.error("Connection error : %s", str(e))

				if self._processing: # don't sleep if Treepuncher is stopping
					await asyncio.sleep(self.cfg.getfloat('reconnect_delay', fallback=5))

		except AuthException as e:
			self.logger.error("Auth exception : [%s|%d] %s (%s)", e.endpoint, e.code, e.data, e.kwargs)
		except InvalidStateError:
			self.logger.error("Invalid authenticator state")
			if isinstance(self.authenticator, MicrosoftAuthenticator):
				self.logger.info("Obtain an auth code by visiting %s", self.authenticator.url())
		except Exception as e:
			self.logger.exception("Unhandled exception : %s", str(e))

		if self._processing:
			await self.stop(force=True)
		self.logger.debug("Worker finished")
