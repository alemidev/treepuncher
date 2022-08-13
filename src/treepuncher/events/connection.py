from aiocraft.mc.definitions import Player
from .base import BaseEvent

class PlayerJoinEvent(BaseEvent):
	player: Player
	
	def __init__(self, p:Player):
		self.player = p

class PlayerLeaveEvent(BaseEvent):
	player: Player

	def __init__(self, p:Player):
		self.player = p
