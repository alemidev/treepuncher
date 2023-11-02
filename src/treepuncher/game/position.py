from typing import Optional

from aiocraft.mc.definitions import BlockPos
from aiocraft.mc.proto import PacketPosition, PacketSetPassengers, PacketEntityTeleport, PacketTeleportConfirm

from ..scaffold import Scaffold

class GamePosition(Scaffold):
	position : BlockPos
	vehicle_id : Optional[int]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.position = BlockPos(0, 0, 0)
		self.vehicle_id = None

		@self.on_packet(PacketSetPassengers)
		async def player_enters_vehicle_cb(packet:PacketSetPassengers):
			if self.vehicle_id is None: # might get mounted on a vehicle
				for entity_id in packet.passengers:
					if entity_id == self.entity_id:
						self.vehicle_id = packet.entityId
			else: # might get dismounted from vehicle
				if packet.entityId == self.vehicle_id:
					if self.entity_id not in packet.passengers:
						self.vehicle_id = None

		@self.on_packet(PacketEntityTeleport)
		async def entity_rubberband_cb(packet:PacketEntityTeleport):
			if self.vehicle_id is None:
				return
			if self.vehicle_id != packet.entityId:
				return
			self.position = BlockPos(packet.x, packet.y, packet.z)
			self.logger.info(
				"Position synchronized : (x:%.0f,y:%.0f,z:%.0f) (vehicle)",
				self.position.x, self.position.y, self.position.z
			)

		@self.on_packet(PacketPosition)
		async def player_rubberband_cb(packet:PacketPosition):
			self.position = BlockPos(packet.x, packet.y, packet.z)
			self.logger.info(
				"Position synchronized : (x:%.0f,y:%.0f,z:%.0f)",
				self.position.x, self.position.y, self.position.z
			)
			await self.dispatcher.write(
				PacketTeleportConfirm(
					self.dispatcher.proto,
					teleportId=packet.teleportId
				)
			)
