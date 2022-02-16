import asyncio
import datetime
import functools

from aiocraft.client import MinecraftClient
from aiocraft.mc.definitions import Gamemode, Dimension, Difficulty
from aiocraft.mc.proto import PacketRespawn, PacketLogin, PacketUpdateHealth, PacketExperience, PacketSettings, PacketClientCommand

from ..events import JoinGameEvent, DeathEvent

class GameState(MinecraftClient):
	hp : float
	food : float
	xp : float
	lvl : int
	total_xp : int

	# TODO player abilities
	# walk_speed : float
	# fly_speed : float
	# flags : int

	in_game : bool
	gamemode : Gamemode
	dimension : Dimension
	difficulty : Difficulty
	join_time : datetime.datetime

	def on_death(self):
		def decorator(fun):
			@functools.wraps(fun)
			async def wrapper():
				event = DeathEvent()
				return await fun(event)
			return self.register(DeathEvent.SENTINEL, wrapper)
		return decorator

	def on_joined_world(self):
		def decorator(fun):
			@functools.wraps(fun)
			async def wrapper():
				event = JoinGameEvent()
				return await fun(event)
			return self.register(JoinGameEvent.SENTINEL, wrapper)
		return decorator

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.in_game = False
		self.gamemode = Gamemode.SURVIVAL
		self.dimension = Dimension.OVERWORLD
		self.difficulty = Difficulty.HARD
		self.join_time = datetime.datetime(2011, 11, 18)

		self.hp = 20.0
		self.food = 20.0
		self.xp = 0.0
		self.lvl = 0

		@self.on_disconnected()
		async def disconnected_cb():
			self.in_game = False

		@self.on_packet(PacketRespawn)
		async def on_player_respawning(packet:PacketRespawn):
			self.gamemode = Gamemode(packet.gamemode)
			self.dimension = Dimension(packet.dimension)
			self.difficulty = Difficulty(packet.difficulty)
			if self.difficulty != Difficulty.PEACEFUL \
			and self.gamemode != Gamemode.SPECTATOR:
				self.in_game = True
			else:
				self.in_game = False
			self._logger.info(
				"Reloading world: %s (%s) in %s",
				self.dimension.name,
				self.difficulty.name,
				self.gamemode.name
			)

		@self.on_packet(PacketLogin)
		async def player_joining_cb(packet:PacketLogin):
			self.gamemode = Gamemode(packet.gameMode)
			self.dimension = Dimension(packet.dimension)
			self.difficulty = Difficulty(packet.difficulty)
			self.join_time = datetime.datetime.now()
			if self.difficulty != Difficulty.PEACEFUL \
			and self.gamemode != Gamemode.SPECTATOR:
				self.in_game = True
			else:
				self.in_game = False
			self._logger.info(
				"Joined world: %s (%s) in %s",
				self.dimension.name,
				self.difficulty.name,
				self.gamemode.name
			)
			self.run_callbacks(JoinGameEvent, self.dimension, self.difficulty, self.gamemode)
			await self.dispatcher.write(
				PacketSettings(
					self.dispatcher.proto,
					locale="en_US",
					viewDistance=4,
					chatFlags=0,
					chatColors=True,
					skinParts=0xF,
					mainHand=0,
				)
			)
			await self.dispatcher.write(PacketClientCommand(self.dispatcher.proto, actionId=0))

		@self.on_packet(PacketUpdateHealth)
		async def player_hp_cb(packet:PacketUpdateHealth):
			died = packet.health != self.hp and packet.health <= 0
			self.hp = packet.health
			self.food = packet.food + packet.foodSaturation
			if died:
				self.run_callbacks(DeathEvent.SENTINEL)
				self._logger.info("Dead, respawning...")
				await asyncio.sleep(0.5)
				await self.dispatcher.write(
					PacketClientCommand(self.dispatcher.proto, actionId=0) # respawn
				)

		@self.on_packet(PacketExperience)
		async def player_xp_cb(packet:PacketExperience):
			if packet.level != self.lvl:
				self._logger.info("Level up : %d", packet.level)
			self.xp = packet.experienceBar
			self.lvl = packet.level
			self.total_xp = packet.totalExperience

