import json
import logging

from typing import TYPE_CHECKING, Dict, Any, Optional, Union, List, Callable, get_type_hints, get_args, get_origin
from dataclasses import dataclass, MISSING, fields

from treepuncher.storage import AddonStorage

from .scaffold import ConfigObject

if TYPE_CHECKING:
	from .treepuncher import Treepuncher

def parse_with_hint(val:str, hint:Any) -> Any:
	if hint is bool:
		if val.lower() in ['1', 'true', 't', 'on', 'enabled']:
			return True
		return False
	if hint is list or get_origin(hint) is list:
		if get_args(hint):
			return list( parse_with_hint(x, get_args(hint)[0]) for x in val.split() )
		return val.split()
	if hint is tuple or get_origin(hint) is tuple:
		if get_args(hint):
			return tuple( parse_with_hint(x, get_args(hint)[0]) for x in val.split() )
		return val.split()
	if hint is set or get_origin(hint) is set:
		if get_args(hint):
			return set( parse_with_hint(x, get_args(hint)[0]) for x in val.split() )
		return set(val.split())
	if hint is dict or get_origin(hint) is dict:
		return json.loads(val)
	if hint is Union or get_origin(hint) is Union:
		for t in get_args(hint):
			if t is type(None) and val in ("null", ""):
				return None
			if t is str:
				continue # try this last, will always succeed
			try:
				return t(val)
			except ValueError:
				pass
		if any(t is str for t in get_args(hint)):
			return str(val)
	return (get_origin(hint) or hint)(val) # try to instantiate directly

class Addon:
	name: str
	config: ConfigObject
	storage: AddonStorage
	logger: logging.Logger

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
		# get_type_hints attempts to instantiate all string hints (such as 'Treepuncher').
		# But we can't import Treepuncher here: would be a cyclic import!
		# We don't care about Treepuncher annotation, so we force it to be None
		cfg_clazz = get_type_hints(type(self), localns={'Treepuncher': None})['config'] # TODO jank localns override
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
		self.storage = client.storage.addon_storage(self.name)
		self.logger = self._client.logger.getChild(self.name)
		self.register()

	def register(self):
		pass

	async def initialize(self):
		pass

	async def cleanup(self):
		pass
