import io
import math
import logging

from typing import Dict, Tuple, Any

import numpy as np

from aiocraft.mc.types import VarInt, Short, UnsignedByte, Type, Context

class BitStream:
	data : bytes
	cursor : int
	size : int

	def __init__(self, data:bytes, size:int):
		self.data = data
		self.cursor = 0
		self.size = size if size > 0 else len(self.data) * 8

	def __len__(self) -> int:
		return self.size - self.cursor

	def read(self, size:int) -> int:
		if len(self) < size:
			raise ValueError(f"Not enough bits ({len(self)} left, {size} requested)")
		start_byte = (self.cursor//8)
		end_byte = math.ceil((self.cursor + size) / 8) + 1
		buf = int.from_bytes(
			self.data[start_byte:end_byte],
			byteorder='little', signed=False
		)
		cut_right = 8 - ((self.cursor + size) % 8)
		self.cursor += size
		return ( buf >> cut_right ) & ( 0xFF >> (8 - (size%8)))

class PalettedContainer(Type):
	pytype : type
	threshold : int
	size : int

	def __init__(self, threshold:int, size:int):
		self.threshold = threshold
		self.size = size

	def write(self, data, buffer:io.BytesIO, ctx:Context):
		raise NotImplementedError

	def read(self, buffer:io.BytesIO, ctx:Context):
		bits = max(UnsignedByte.read(buffer, ctx=ctx), 4)
		if bits > 13:
			raise ValueError("Bits Per Bit too high : %d", bits)
		palette = np.empty((0,), dtype='int32')
		palette_len = VarInt.read(buffer, ctx=ctx)
		if bits < self.threshold:
			palette = np.zeros((palette_len,), dtype='int32')
			for i in range(palette_len):
				palette[i] = VarInt.read(buffer, ctx=ctx)
		size = VarInt.read(buffer, ctx=ctx)
		stream = BitStream(buffer.read(size * 8), size*8*8) # a Long is 64 bits long
		section = np.zeros((self.size, self.size, self.size), dtype='int32')
		index = 0
		for y in range(self.size):
			for z in range(self.size):
				for x in range(self.size):
					val = stream.read(bits)
					section[x, y, z] = palette[val] if bits < self.threshold else val
		return section

BiomeContainer = PalettedContainer(4, 4)
BlockStateContainer = PalettedContainer(9, 16)

class NewChunkSectionType(Type):
	pytype : type

	def write(self, data, buffer:io.BytesIO, ctx:Context):
		raise NotImplementedError

	def read(self, buffer:io.BytesIO, ctx:Context):
		block_count = Short.read(buffer, ctx=ctx)
		block_states = BlockStateContainer.read(buffer, ctx=ctx)
		biomes = BiomeContainer.read(buffer, ctx=ctx)
		return (
			block_count,
			block_states,
			biomes
		)

class OldChunkSectionType(Type):
	pytype : type

	def write(self, data, buffer:io.BytesIO, ctx:Context):
		raise NotImplementedError

	def read(self, buffer:io.BytesIO, ctx:Context):
		section = BlockStateContainer.read(buffer, ctx=ctx)
		block_light = np.empty((16, 16, 16), dtype='int32')
		block_light_buffer = BitStream(buffer.read(2048), 2048*8)
		for y in range(16):
			for z in range(16):
				for x in range(16):
					block_light[x, y, z] = block_light_buffer.read(4)
		sky_light = np.empty((16, 16, 16), dtype='int32')
		if ctx.overworld:
			sky_light_buffer = BitStream(buffer.read(2048), 2048*8)
			for y in range(16):
				for z in range(16):
					for x in range(16):
						sky_light[x, y, z] = sky_light_buffer.read(4)
		return (
			section,
			block_light,
			sky_light
		)


ChunkSection = OldChunkSectionType()

class Chunk(Type):
	x : int
	z : int
	bitmask : int
	ground_up_continuous : bool
	blocks : np.ndarray
	block_light : np.ndarray
	sky_light : np.ndarray
	biomes: bytes

	def __init__(self, x:int, z:int, bitmask:int, ground_up_continuous:bool):
		self.x = x
		self.z = z
		self.bitmask = bitmask
		self.blocks = np.zeros((16, 256, 16), dtype='int32')
		self.block_light = np.zeros((16, 256, 16), dtype='int32')
		self.sky_light = np.zeros((16, 256, 16), dtype='int32')
		self.ground_up_continuous = ground_up_continuous

	def __getitem__(self, item:Any):
		return self.blocks[item]

	def read(self, buffer:io.BytesIO, ctx:Context):
		logging.info("Reading chunk")
		for i in range(16):
			if (self.bitmask >> i) & 1:
				section, block_light, sky_light = ChunkSection.read(buffer, ctx=ctx)
				self.blocks[:, i*16 : (i+1)*16, :] = section
				self.block_light[:, i*16 : (i+1)*16, :] = block_light
				self.sky_light[:, i*16 : (i+1)*16, :] = sky_light
		if self.ground_up_continuous:
			self.biomes = buffer.read(256) # 16x16
		return self

class World:
	chunks : Dict[Tuple[int, int], Chunk]

	def __init__(self):
		self.chunks = {}

	def __getitem__(self, item:Tuple[int, int, int]):
		return self.get(*item)

	def get(self, x:int, y:int, z:int) -> int:
		coord = (x//16, z//16)
		if coord not in self.chunks:
			raise KeyError(f"Chunk {coord} not loaded")
		return self.chunks[coord][int(x%16), int(y), int(z%16)]

	def put(self, chunk:Chunk, x:int, z:int):
		self.chunks[(x,z)] = chunk

	

