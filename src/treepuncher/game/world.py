import uuid
import datetime

from typing import Dict, List

from aiocraft.mc.definitions import BlockPos
from aiocraft.mc.proto import PacketPosition, PacketTeleportConfirm

from ..scaffold import Scaffold
from ..events import ConnectedEvent

class GameWorld(Scaffold):
	position : BlockPos
	# TODO world

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.position = BlockPos(0, 0, 0)

		@self.on(ConnectedEvent)
		async def connected_cb(_):
			self.tablist.clear()

		@self.on_packet(PacketPosition)
		async def player_rubberband_cb(packet:PacketPosition):
			self.position = BlockPos(packet.x, packet.y, packet.z)
			self._logger.info(
				"Position synchronized : (x:%.0f,y:%.0f,z:%.0f)",
				self.position.x, self.position.y, self.position.z
			)
			await self.dispatcher.write(
				PacketTeleportConfirm(
					self.dispatcher.proto,
					teleportId=packet.teleportId
				)
			)
