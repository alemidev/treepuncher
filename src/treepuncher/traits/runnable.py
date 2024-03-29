import asyncio
import logging

from typing import Optional
from signal import signal, SIGINT, SIGTERM

class Runnable:
	_is_running : bool
	_stop_task : Optional[asyncio.Task]
	_loop : asyncio.AbstractEventLoop

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._is_running = False
		self._stop_task = None
		self._loop = asyncio.get_event_loop()

	async def start(self):
		self._is_running = True

	async def stop(self, force:bool=False):
		self._is_running = False

	def run(self):
		logging.info("Starting process")

		def signal_handler(signum, __):
			if signum == SIGINT:
				if self._stop_task:
					self._stop_task.cancel()
					logging.info("Received SIGINT, terminating")
				else:
					logging.info("Received SIGINT, stopping gracefully...")
				self._stop_task = asyncio.get_event_loop().create_task(self.stop(force=self._stop_task is not None))
			if signum == SIGTERM:
				logging.info("Received SIGTERM, terminating")
				self._stop_task = asyncio.get_event_loop().create_task(self.stop(force=True))


		signal(SIGINT, signal_handler)

		async def main():
			await self.start()
			while self._is_running:
				await asyncio.sleep(1)

		self._loop.run_until_complete(main())

		logging.info("Process finished")

