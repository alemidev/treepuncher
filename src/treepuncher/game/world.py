import json

from aiocraft.mc.definitions import BlockPos
from aiocraft.mc.proto import PacketMapChunk, PacketBlockChange, PacketMultiBlockChange
from aiocraft.mc.types import twos_comp

from aiocraft import Chunk, World  # TODO these imports will hopefully change!

from ..scaffold import Scaffold
from ..events import BlockUpdateEvent

class GameWorld(Scaffold):
	world : World

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.world = World()

		# Since this might require more resources, allow to disable it
		if not self.cfg.getboolean("process_world", fallback=True):
			return

		if self.dispatcher.proto == 340: # Chunk parsing is only implemented for 1.12
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
			await self.run_callbacks(BlockUpdateEvent, BlockUpdateEvent(pos, packet.type))

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
					await self.run_callbacks(BlockUpdateEvent, BlockUpdateEvent(pos, entry['blockId']))
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
					await self.run_callbacks(BlockUpdateEvent, BlockUpdateEvent(pos, state))
			else:
				self.logger.error("Cannot process MultiBlockChange for protocol %d", self.dispatcher.proto)
