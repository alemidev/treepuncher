from aiocraft.mc.definitions import BlockPos

from .base import BaseEvent

class BlockUpdateEvent(BaseEvent):
	SENTINEL = object()

	location : BlockPos
	state    : int

	def __init__(self, location: BlockPos, state: int):
		self.location = location
		self.state = state
