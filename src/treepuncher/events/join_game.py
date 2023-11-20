from aiocraft.types import Dimension, Difficulty, Gamemode

from .base import BaseEvent

class JoinGameEvent(BaseEvent):
	SENTINEL = object()

	dimension : Dimension
	difficulty : Difficulty
	gamemode : Gamemode

	def __init__(self, dimension:Dimension, difficulty:Difficulty, gamemode:Gamemode):
		self.gamemode = gamemode
		self.difficulty = difficulty
		self.dimension = dimension
