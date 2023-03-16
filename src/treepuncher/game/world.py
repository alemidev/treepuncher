import json

from time import time
from typing import Optional

from aiocraft.mc.definitions import BlockPos
from aiocraft.mc.proto.play.clientbound import (
	PacketPosition, PacketMapChunk, PacketBlockChange, PacketMultiBlockChange, PacketSetPassengers,
	PacketEntityTeleport, PacketRelEntityMove
)
from aiocraft.mc.proto.play.serverbound import PacketTeleportConfirm, PacketSteerVehicle
from aiocraft import Chunk, World  # TODO these imports will hopefully change!

from ..scaffold import Scaffold

class GameWorld(Scaffold):
	position : BlockPos
	vehicle_id : Optional[int]
	world : World

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
			self.logger.info(
				"Position synchronized : (x:%.0f,y:%.0f,z:%.0f) (relMove vehicle)",
				self.position.x, self.position.y, self.position.z
			)

		@self.scheduler.scheduled_job('interval', seconds=5, name='send steer vehicle if riding a vehicle')
		async def steer_vehicle_cb():
			if self.vehicle_id is None:
				return
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

		if self.cfg.getboolean("process_world", fallback=False):
			self.world = World()

			@self.on_packet(PacketMapChunk)
			async def map_chunk_cb(packet:PacketMapChunk):
				assert isinstance(packet.bitMap, int)
				c = Chunk(packet.x, packet.z, packet.bitMap, packet.groundUp, json.dumps(packet.blockEntities))  # TODO a solution which is not jank!
				c.read(packet.chunkData)
				self.world.put(c, packet.x, packet.z, not packet.groundUp)

			@self.on_packet(PacketBlockChange)
			async def block_change_cb(packet:PacketBlockChange):
				self.world.put_block(packet.location[0], packet.location[1], packet.location[2], packet.type)

			@self.on_packet(PacketMultiBlockChange)
			async def multi_block_change_cb(packet:PacketMultiBlockChange):
				chunk_x_off = packet.chunkX * 16
				chunk_z_off = packet.chunkZ * 16
				for entry in packet.records:
					x_off = (entry['horizontalPos'] >> 4 ) & 15
					z_off = entry['horizontalPos'] & 15
					self.world.put_block(x_off + chunk_x_off, entry['y'], z_off + chunk_z_off, entry['blockId'])
