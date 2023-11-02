import json
from time import time

from aiocraft.mc.definitions import BlockPos
from aiocraft.mc.proto import (
	PacketMapChunk, PacketBlockChange, PacketMultiBlockChange, PacketSetPassengers, PacketEntityTeleport,
	PacketSteerVehicle, PacketRelEntityMove, PacketTeleportConfirm, PacketPosition
)
from aiocraft.mc.types import twos_comp

from aiocraft import Chunk, World  # TODO these imports will hopefully change!

from ..scaffold import Scaffold
from ..events import BlockUpdateEvent

class GameWorld(Scaffold):
	position : BlockPos
	vehicle_id : int | None
	world : World

	_last_steer_vehicle : float

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.position = BlockPos(0, 0, 0)
		self.vehicle_id = None
		self._last_steer_vehicle = time()

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

		@self.on_packet(PacketRelEntityMove)
		async def entity_relative_move_cb(packet:PacketRelEntityMove):
			if self.vehicle_id is None:
				return
			if self.vehicle_id != packet.entityId:
				return
			self.position = BlockPos(
				self.position.x + packet.dX,
				self.position.y + packet.dY,
				self.position.z + packet.dZ
			)
			self.logger.debug(
				"Position synchronized : (x:%.0f,y:%.0f,z:%.0f) (relMove vehicle)",
				self.position.x, self.position.y, self.position.z
			)
			if time() - self._last_steer_vehicle >= 5:
				self._last_steer_vehicle = time()
				await self.dispatcher.write(
					PacketSteerVehicle(
						self.dispatcher.proto,
						forward=0,
						sideways=0,
						jump=0
					)
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

		# Since this might require more resources, allow to disable it
		if not self.cfg.getboolean("process_world", fallback=True):
			return

		@self.on_packet(PacketMapChunk)
		async def map_chunk_cb(packet:PacketMapChunk):
			assert isinstance(packet.bitMap, int)
			c = Chunk(packet.x, packet.z, packet.bitMap, packet.groundUp, json.dumps(packet.blockEntities))  # TODO a solution which is not jank!
			c.read(packet.chunkData)
			self.world.put(c, packet.x, packet.z, not packet.groundUp)

		@self.on_packet(PacketBlockChange)
		async def block_change_cb(packet:PacketBlockChange):
			self.world.put_block(packet.location[0], packet.location[1], packet.location[2], packet.type)
			pos = BlockPos(packet.location[0], packet.location[1], packet.location[2])
			self.run_callbacks(BlockUpdateEvent, BlockUpdateEvent(pos, packet.type))

		@self.on_packet(PacketMultiBlockChange)
		async def multi_block_change_cb(packet:PacketMultiBlockChange):
			if self.dispatcher.proto < 751:
				chunk_x_off = packet.chunkX * 16
				chunk_z_off = packet.chunkZ * 16
				for entry in packet.records:
					x_off = (entry['horizontalPos'] >> 4 ) & 15
					z_off = entry['horizontalPos'] & 15
					pos = BlockPos(x_off + chunk_x_off, entry['y'], z_off + chunk_z_off)
					self.world.put_block(pos.x,pos.y, pos.z, entry['blockId'])
					self.run_callbacks(BlockUpdateEvent, BlockUpdateEvent(pos, entry['blockId']))
			elif self.dispatcher.proto < 760:
				x = twos_comp((packet.chunkCoordinates >> 42) & 0x3FFFFF, 22)
				z = twos_comp((packet.chunkCoordinates >> 20) & 0x3FFFFF, 22)
				y = twos_comp((packet.chunkCoordinates      ) & 0xFFFFF , 20)
				for loc in packet.records:
					state = loc >> 12
					dx = ((loc & 0x0FFF) >> 8 ) & 0x0F
					dz = ((loc & 0x0FFF) >> 4 ) & 0x0F
					dy = ((loc & 0x0FFF)      ) & 0x0F
					pos = BlockPos(16*x + dx, 16*y + dy, 16*z + dz)
					self.world.put_block(pos.x, pos.y, pos.z, state)
					self.run_callbacks(BlockUpdateEvent, BlockUpdateEvent(pos, state))
			else:
				self.logger.error("Cannot process MultiBlockChange for protocol %d", self.dispatcher.proto)
