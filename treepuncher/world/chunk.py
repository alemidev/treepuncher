import io

from typing import Dict, Tuple, Any

import numpy as np

from aiocraft.mc.types import VarInt, Short, UnsignedByte, Type

class BitStream:
	data : bytes
	cursor : int
	size : int

	def __init__(self, data:bytes, size:int=-1):
		self.data = data
		self.cursor = 0
		self.size = size if size > 0 else len(self.data) * 8

	def __len__(self) -> int:
		return self.size - self.cursor

	def read(self, size:int) -> int:
		if len(self) < size:
			raise ValueError("Not enough bits")
		aligned_size = (size//8)+1
		buf = int.from_bytes(
			self.data[self.cursor:aligned_size],
			byteorder='little', signed=False
		)
		self.cursor += size
		delta = aligned_size - size
		return ( buf << delta ) >> delta

class PalettedContainer(Type):
	pytype : type
	threshold : int
	maxsize : int

	def __init__(self, threshold:int, maxsize:int):
		self.threshold = threshold
		self.maxsize = maxsize

	def write(self, data, buffer:io.BytesIO, ctx:object=None):
		raise NotImplementedError

	def read(self, buffer:io.BytesIO, ctx:object=None):
		bits = UnsignedByte.read(buffer, ctx=ctx)
		palette = np.empty((0,), dtype='int32')
		if bits == 0:
			value = VarInt.read(buffer, ctx=ctx)
		elif bits < self.threshold:
			palette_len = VarInt.read(buffer, ctx=ctx)
			palette = np.zeros((palette_len,), dtype='int32')
			for i in range(palette_len):
				palette[i] = VarInt.read(buffer)
		size = VarInt.read(buffer, ctx=ctx)
		stream = BitStream(buffer.read(size * 8))
		section = np.zeros((self.maxsize,), dtype='int32')
		index = 0
		while index < self.maxsize and len(stream) > 0:
			val = stream.read(bits) if bits > 0 else value
			section[index] = palette[val] if bits < self.threshold and bits > 0 else val
			index+=1
		return section

BiomeContainer = PalettedContainer(4, 64)
BlockStateContainer = PalettedContainer(9, 4096)

class ChunkSectionType(Type):
	pytype : type

	def write(self, data, buffer:io.BytesIO, ctx:object=None):
		raise NotImplementedError

	def read(self, buffer:io.BytesIO, ctx:object=None):
		block_count = Short.read(buffer)
		block_states = BlockStateContainer.read(buffer)
		biomes = BiomeContainer.read(buffer)
		return (
			block_count,
			block_states.reshape((16, 16, 16)),
			biomes.reshape((4, 4, 4))
		)

ChunkSection = ChunkSectionType()

class Chunk(Type):
	x : int
	z : int
	bitmask : int
	blocks : np.ndarray
	biomes : np.ndarray
	block_count : int

	def __init__(self, x:int, z:int, bitmask:int):
		self.x = x
		self.z = z
		self.bitmask = bitmask
		self.blocks = np.zeros((16, 256, 16))
		self.biomes = np.zeros((4, 64, 4))
		self.block_count = 0

	def __getitem__(self, item:Any):
		return self.blocks[item]

	def read(self, buffer:io.BytesIO, ctx:object=None):
		for i in range(16):
			if (self.bitmask >> i) & 1:
				block_count, block_states, biomes = ChunkSection.read(buffer)
				self.block_count += block_count
				self.blocks[:, i*16 : (i+1)*16, :] = block_states
				self.biomes[:, i*4 : (i+1)*4, :] = biomes
		return self

class World:
	chunks : Dict[Tuple[int, int], Chunk]

	def __init__(self):
		self.chunks = {}

	def __getitem__(self, item:Tuple[int, int, int]):
		return self.get(*item)

	def get(self, x:int, y:int, z:int):
		coord = (x//16, z//16)
		if coord not in self.chunks:
			raise KeyError(f"Chunk {coord} not loaded")
		return self.chunks[coord][x%16, y, z%16]

	def put(self, chunk:Chunk, x:int, z:int):
		self.chunks[(x,z)] = chunk

	

