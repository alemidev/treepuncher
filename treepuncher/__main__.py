#!/usr/bin/env python
import os
import re
import asyncio
import logging
import argparse

from pathlib import Path
from importlib import import_module
from typing import get_type_hints
from dataclasses import dataclass

from setproctitle import setproctitle

from .treepuncher import Treepuncher, Addon, ConfigObject
from .helpers import configure_logging

def main():
	root = Path(os.getcwd())
	# TODO would be cool if it was possible to configure addons path, but we need to load addons before doing argparse so we can do helptext
	# addon_path = Path(args.path) if args.addon_path else ( root/'addons' )
	addon_path = root/'addons'
	addons : List[Type[Addon]] = []

	for path in sorted(addon_path.rglob('*.py')):
		m = import_module(path)
		for obj_name in vars(m).keys():
			obj = getattr(m, obj_name)
			if issubclass(obj, Addon):
				addons.append(obj)

	class ChatLogger(Addon):
		"""print (optionally colored) game chat to terminal"""
		REMOVE_COLOR_FORMATS = re.compile(r"§[0-9a-z]")
		@dataclass
		class Options(ConfigObject):
			test : str
			something : int
			color : bool = True
			blah : str = 'porcodio'

		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			@self.on_packet(PacketChatMessage)
			async def print_chat_colored_to_terminal(packet:PacketChatMessage):
				print(self.REMOVE_COLOR_FORMATS.sub("", parse_chat(packet.message, ansi_color=self.config.color)))

	addons.append(ChatLogger)

	class ChatInput(Addon):
		"""read input from stdin and send to game chat"""
		task : asyncio.Task
		running : bool

		def __init__(self, *args, **kwargs):
			super().__init__(*args, **kwargs)
			self.task = None
			self.running = False
	
		async def initialize(self):
			async def aio_input():
				while self.running:
					try:
						await self.client.chat(await asyncio.wait_for(ainput(""), 1))
					except asyncio.TimeoutError:
						pass
					except Exception:
						client._logger.exception("Exception processing input from keyboard")
			self.running = True
			self.task = asyncio.get_event_loop().create_task(aio_input())
	
		async def cleanup(self, force:bool=False):
			self.running = False
			if self.task and not force:
				await self.task

	addons.append(ChatInput)

	help_text = '\n\naddons:\n' + str.join( # TODO do this iteratively to make it readable!
		'\n', (
			f"  {addon.__name__}\t\t{addon.__doc__ or '-no description-'}\n    " + str.join('\n    ',
				(f"* {name} ({clazz.__name__}) {'[required]' if not hasattr(addon.Options, name) else ''}" for (name, clazz) in get_type_hints(addon.Options).items())
			) for addon in addons
		)
	)

	parser = argparse.ArgumentParser(
		prog='python -m treepuncher',
		description='Treepuncher | Block Game automation framework',
		epilog=help_text,
		formatter_class=argparse.RawDescriptionHelpFormatter,
	)

	parser.add_argument('name', help='name to use for this client session')
	parser.add_argument('server', help='server to connect to')
	parser.add_argument('--client-id', dest='cid', default='c63ef189-23cb-453b-8060-13800b85d2dc', help='client_id of your Azure application')
	parser.add_argument('--secret', dest='secret', default='N2e7Q~ybYA0IO39KB1mFD4GmoYzISRaRNyi59', help='client_secret of your Azure application')
	parser.add_argument('--redirect-uri', dest='uri', default='https://fantabos.co/msauth', help='redirect_uri of your Azure application')
	parser.add_argument('--addon-path', dest='path', default='', help='path for loading addons')
	parser.add_argument('--chat-log', dest='chat_log', action='store_const', const=True, default=False, help="print (colored) chat to terminal")
	parser.add_argument('--chat-input', dest='chat_input', action='store_const', const=True, default=False, help="read input from stdin and send it to chat")
	parser.add_argument('--debug', dest='_debug', action='store_const', const=True, default=False, help="enable debug logs")
	parser.add_argument('--no-packet-whitelist', dest='use_packet_whitelist', action='store_const', const=False, default=True, help="disable packet whitelist")

	args = parser.parse_args()

	configure_logging(args.name, level=logging.DEBUG if args._debug else logging.INFO)
	setproctitle(f"treepuncher[{args.name}]")

	code = input(f"-> Go to 'https://fantabos.co/msauth?client_id={args.cid}&state=hardcoded', click 'Auth' and login, then copy here the code you received\n--> ")

	client = Treepuncher(
		args.name,
		args.server,
		use_packet_whitelist=use_packet_whitelist,
		notifier=notifier,
		client_id=args.cid,
		client_secret=args.secret,
		redirect_uri=args.uri
	)

	for addon in addons:
		client.install(addon)

	if args.chat_log:
		client.install(ChatLogger)

	if args.chat_input:
		from aioconsole import ainput
		client.install(ChatInput)

	client.run()

if __name__ == "__main__":
	main()


