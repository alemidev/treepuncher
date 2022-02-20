from aiocraft.mc.definitions import Dimension, Difficulty, Gamemode

from .base import BaseEvent

class JoinGameEvent(BaseEvent):
	SENTINEL = object()

	dimension : Dimension
	difficulty : Difficulty
	gamemode : Gamemode
