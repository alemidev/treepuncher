#!/usr/bin/env python
import os
import re
import asyncio
import logging
import argparse
import inspect

from pathlib import Path
from importlib import import_module
from typing import get_type_hints
from dataclasses import dataclass, MISSING

from setproctitle import setproctitle

from .treepuncher import Treepuncher, Addon, ConfigObject
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

	help_text = '\n\naddons:'

	for addon in addons:
		help_text += f"\n  {addon.__name__} \t{addon.__doc__ or ''}"
		cfg_clazz = get_type_hints(addon)['config']
		for name, field in cfg_clazz.__dataclass_fields__.items():
			default = field.default if field.default is not MISSING \
				else field.default_factory() if field.default_factory is not MISSING \
				else MISSING
			help_text += f"\n    * {name} ({field.type.__name__}) | {'-required-' if default is MISSING else f'{default}'}"
	help_text += '\n'

	parser = argparse.ArgumentParser(
		prog='python -m treepuncher',
		description='Treepuncher | Block Game automation framework',
		epilog=help_text,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)

	parser.add_argument('name', help='name to use for this client session')
	parser.add_argument('server', help='server to connect to')
	parser.add_argument('-c', '--code', dest='code', action='store_const', const=True, default=False, help="request new code to login")
	parser.add_argument('--client-id', dest='cid', default='c63ef189-23cb-453b-8060-13800b85d2dc', help='client_id of your Azure application')
	parser.add_argument('--secret', dest='secret', default='N2e7Q~ybYA0IO39KB1mFD4GmoYzISRaRNyi59', help='client_secret of your Azure application')
	parser.add_argument('--redirect-uri', dest='uri', default='https://fantabos.co/msauth', help='redirect_uri of your Azure application')
	parser.add_argument('--addon-path', dest='path', default='', help='path for loading addons')
	parser.add_argument('--chat-log', dest='chat_log', action='store_const', const=True, default=False, help="print (colored) chat to terminal")
	parser.add_argument('--chat-input', dest='chat_input', action='store_const', const=True, default=False, help="read input from stdin and send it to chat")
	parser.add_argument('--debug', dest='_debug', action='store_const', const=True, default=False, help="enable debug logs")
	parser.add_argument('--no-packet-filter', dest='use_packet_whitelist', action='store_const', const=False, default=True, help="disable packet whitelist, will decrease performance")

	args = parser.parse_args()

	configure_logging(args.name, level=logging.DEBUG if args._debug else logging.INFO)
	setproctitle(f"treepuncher[{args.name}]")

	code = None
	if args.code:
		code = input(f"-> Go to 'https://fantabos.co/msauth?client_id={args.cid}&state=hardcoded', click 'Auth' and login, then copy here the code you received\n--> ")

	client = Treepuncher(
		args.name,
		args.server,
		use_packet_whitelist=use_packet_whitelist,
		login_code=code,
		client_id=args.cid,
		client_secret=args.secret,
		redirect_uri=args.uri
	)

	for addon in addons:
		client.install(addon)

	client.run()

if __name__ == "__main__":
	main()


