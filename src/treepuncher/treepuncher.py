import re
import json
import logging
import asyncio
import datetime
import uuid
import pkg_resources

from typing import List, Dict, Optional, Union, Any, Type, get_args, get_origin, get_type_hints, Set, Callable
from time import time
from dataclasses import dataclass, MISSING, fields
from configparser import ConfigParser

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiocraft.mc.packet import Packet
from aiocraft.mc.auth import AuthInterface, AuthException, MojangAuthenticator, MicrosoftAuthenticator, OfflineAuthenticator

from .storage import Storage, SystemState, AuthenticatorState
from .game import GameState, GameChat, GameInventory, GameTablist, GameWorld

__VERSION__ = pkg_resources.get_distribution('treepuncher').version

def parse_with_hint(val:str, hint:Any) -> Any:
	if hint is bool:
		if val.lower() in ['1', 'true', 't', 'on', 'enabled']:
			return True
		return False
	if hint is list or get_origin(hint) is list:
		if get_args(hint):
			return [ parse_with_hint(x, get_args(hint)[0]) for x in val.split() ]
		return val.split()
	if hint is set or get_origin(hint) is set:
		if get_args(hint):
			return set( parse_with_hint(x, get_args(hint)[0]) for x in val.split() )
		return set(val.split())
	if hint is dict or get_origin(hint) is dict:
		return json.loads(val)
	if hint is Union or get_origin(hint) is Union:
		for t in get_args(hint):
			try:
				return t(val)
			except ValueError:
				pass
	return (get_origin(hint) or hint)(val) # try to instantiate directly

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
			for field in fields(cfg_clazz):
				default = field.default if field.default is not MISSING \
					else field.default_factory() if field.default_factory is not MISSING \
					else MISSING
				if cfg.has_option(self.name, field.name):
					opts[field.name] = parse_with_hint(self._client.config[self.name].get(field.name), field.type)
				elif default is MISSING:
					repr_type = field.type.__name__ if isinstance(field.type, type) else str(field.type) # TODO fix for 3.8 I think?
					raise ValueError(
						f"Missing required value '{field.name}' of type '{repr_type}' in section '{self.name}'"
					)
				else:  # not really necessary since it's a dataclass but whatever
					opts[field.name] = default
		self.config = self.Options(**opts)
		self.register()

	def register(self):
		pass

	async def initialize(self):
		pass

	async def cleanup(self):
		pass

class Notifier(Addon): # TODO this should be an Addon too!
	_report_functions : List[Callable]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
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
		if not self.notifier:
			self.notifier = Notifier(self)
		for m in self.modules:
			await m.initialize()
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
			for m in self.modules:
				await m.cleanup()
			await self.join_callbacks()
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
			if "version" in server_data and "protocol" in server_data["version"]:
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
				await asyncio.sleep(self.config['Treepuncher'].getfloat('reconnect_delay', fallback=5))
		if self._processing:
			await self.stop(force=True)
