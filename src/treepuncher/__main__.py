#!/usr/bin/env python
import os
import re
import asyncio
import logging
import argparse
import inspect

from pathlib import Path
from importlib import import_module
from typing import List, Type, get_type_hints
from dataclasses import dataclass, MISSING, fields

from setproctitle import setproctitle

from .treepuncher import Treepuncher, MissingParameterError, Addon, ConfigObject, Notifier
from .helpers import configure_logging

def main():
	root = Path(os.getcwd())
	# TODO would be cool if it was possible to configure addons path, but we need to load addons before doing argparse so we can do helptext
	# addon_path = Path(args.path) if args.addon_path else ( root/'addons' )
	addon_path = Path('addons')
	addons : List[Type[Addon]] = []

	for path in sorted(addon_path.rglob('*.py')):
		py_path = str(path).replace('/', '.').replace('.py', '')
		m = import_module(py_path)
		for obj_name in vars(m).keys():
			obj = getattr(m, obj_name)
			if obj != Addon and inspect.isclass(obj) and issubclass(obj, Addon):
				addons.append(obj)
				break

	help_text = '\n\naddons:'

	for addon in addons:
		help_text += f"\n  {addon.__name__} \t{addon.__doc__ or ''}"
		cfg_clazz = get_type_hints(addon)['config']
		if cfg_clazz is ConfigObject:
			continue # it's the superclass type hint
		for field in fields(cfg_clazz):
			default = field.default if field.default is not MISSING \
				else field.default_factory() if field.default_factory is not MISSING \
				else MISSING
			repr_type = field.type.__name__ if isinstance(field.type, type) else str(field.type) # TODO fix for 3.8 I think?
			help_text += f"\n    * {field.name} ({repr_type}) | {'-required-' if default is MISSING else f'{default}'}"
	help_text += '\n'

	parser = argparse.ArgumentParser(
		prog='python -m treepuncher',
		description='Treepuncher | Block Game automation framework',
		epilog=help_text,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)

	parser.add_argument('name', help='name to use for this client session')

	parser.add_argument('--server', dest='server', default='', help='server to connect to')
	parser.add_argument('--debug', dest='_debug', action='store_const', const=True, default=False, help="enable debug logs")
	parser.add_argument('--no-packet-filter', dest='use_packet_whitelist', action='store_const', const=False, default=True, help="disable packet whitelist, will decrease performance")

	parser.add_argument('--code', dest='code', default='', help='login code for oauth2 flow')

	parser.add_argument('--mojang', dest='mojang', action='store_const', const=True, default=False, help="use legacy Mojang authenticator")
	parser.add_argument('--print-token', dest='print_token', action='store_const', const=True, default=False, help="show legacy token before stopping")

	parser.add_argument('--addon-path', dest='path', default='', help='path for loading addons')
	parser.add_argument('--chat-log', dest='chat_log', action='store_const', const=True, default=False, help="print (colored) chat to terminal")
	parser.add_argument('--chat-input', dest='chat_input', action='store_const', const=True, default=False, help="read input from stdin and send it to chat")
	parser.add_argument('--addons', dest='add', nargs='+', type=str, default=None, help='specify addons to enable, defaults to all')
	# TODO find a better way to specify which addons are enabled

	args = parser.parse_args()

	configure_logging(args.name, level=logging.DEBUG if args._debug else logging.INFO)
	setproctitle(f"treepuncher[{args.name}]")

	kwargs = {}

	if args.server:
		kwargs["server"] = args.server

	try:
		client = Treepuncher(
			args.name,
			args.server,
			legacy=args.mojang,
			use_packet_whitelist=args.use_packet_whitelist,
		)
	except MissingParameterError as e:
		return logging.error(e.args[0])

	enabled_addons = set(
		a.lower() for a in (
			args.add if args.add is not None else client.config.sections()
		)
	)

	# TODO ugly af! notifiers get installed first tho

	for addon in addons:
		if addon.__name__.lower() in enabled_addons and issubclass(addon, Notifier):
			logging.info("Installing '%s'", addon.__name__)
			client.install(addon)

	for addon in addons:
		if addon.__name__.lower() in enabled_addons and not issubclass(addon, Notifier):
			logging.info("Installing '%s'", addon.__name__)
			client.install(addon)

	client.run()

	if args.print_token:
		logging.info("Token: %s", client.authenticator.serialize())

if __name__ == "__main__":
	main()


