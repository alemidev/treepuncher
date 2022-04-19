import json
from typing import Any, Dict, List, Set, get_type_hints, get_args, get_origin
from dataclasses import dataclass, MISSING, fields

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