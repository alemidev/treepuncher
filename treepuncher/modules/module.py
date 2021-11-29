
class LogicModule:
	def register(self, client:'Treepuncher') -> None:
		pass # override to register callbacks on client

	async def initialize(self, client:'Treepuncher') -> None:
		pass # override to register stuff on client start

	async def cleanup(self, client:'Treepuncher') -> None:
		pass # override to register stuff on client stop

