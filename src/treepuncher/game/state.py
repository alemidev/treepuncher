import asyncio
import datetime
import json

#from aiocraft.client import MinecraftClient
from aiocraft.types import Gamemode, Dimension, Difficulty
from aiocraft.proto import (
	PacketRespawn, PacketLogin, PacketUpdateHealth, PacketExperience, PacketSettings,
	PacketClientCommand, PacketAbilities, PacketDifficulty
)

from ..events import JoinGameEvent, DeathEvent, DisconnectedEvent
from ..scaffold import Scaffold

class GameState(Scaffold):
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

	# Abilities
	flags : int
	flyingSpeed : float
	walkingSpeed : float

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.in_game = False
		self.gamemode = Gamemode.UNKNOWN
		self.dimension = Dimension.UNKNOWN
		self.difficulty = Difficulty.UNKNOWN
		self.join_time = datetime.datetime(2011, 11, 18)

		self.hp = 20.0
		self.food = 20.0
		self.xp = 0.0
		self.lvl = 0
		self.total_xp = 0

		@self.on(DisconnectedEvent)
		async def disconnected_cb(_):
			self.in_game = False

		@self.on_packet(PacketRespawn)
		async def on_player_respawning(packet:PacketRespawn):
			self.gamemode = Gamemode(packet.gamemode)
			if isinstance(packet.dimension, dict):
				self.logger.info("Received dimension data: %s", json.dumps(packet.dimension, indent=2))
				self.dimension = Dimension.from_str(packet.dimension['effects'])
			else:
				self.dimension = Dimension(packet.dimension)
				self.difficulty = Difficulty(packet.difficulty)
			if self.difficulty != Difficulty.PEACEFUL \
			and self.gamemode != Gamemode.SPECTATOR:
				self.in_game = True
			else:
				self.in_game = False
			self.logger.info(
				"Reloading world: %s (%s) in %s",
				self.dimension.name,
				self.difficulty.name,
				self.gamemode.name
			)

		@self.on_packet(PacketDifficulty)
		async def on_set_difficulty(packet:PacketDifficulty):
			self.difficulty = Difficulty(packet.difficulty)
			self.logger.info("Difficulty set to %s", self.difficulty.name)

		@self.on_packet(PacketLogin)
		async def player_joining_cb(packet:PacketLogin):
			self.entity_id = packet.entityId
			self.gamemode = Gamemode(packet.gameMode)
			if isinstance(packet.dimension, dict):
				with open('world_codec.json', 'w') as f:
					json.dump(packet.dimensionCodec, f)
				self.dimension = Dimension.from_str(packet.dimension['effects'])
			else:
				self.dimension = Dimension(packet.dimension)
				self.difficulty = Difficulty(packet.difficulty)
			self.join_time = datetime.datetime.now()
			if self.difficulty != Difficulty.PEACEFUL \
			and self.gamemode != Gamemode.SPECTATOR:
				self.in_game = True
			else:
				self.in_game = False
			self.logger.info(
				"Joined world: %s (%s) in %s",
				self.dimension.name,
				self.difficulty.name,
				self.gamemode.name
			)
			self.run_callbacks(JoinGameEvent, JoinGameEvent(self.dimension, self.difficulty, self.gamemode))
			await self.dispatcher.write(
				PacketSettings(
					locale="en_US",
					viewDistance=4,
					chatFlags=0,
					chatColors=True,
					skinParts=0xF,
					mainHand=0,
				)
			)
			await self.dispatcher.write(PacketClientCommand(actionId=0))

		@self.on_packet(PacketUpdateHealth)
		async def player_hp_cb(packet:PacketUpdateHealth):
			died = packet.health != self.hp and packet.health <= 0
			if self.hp != packet.health:
				if self.hp < packet.health:
					self.logger.info("Healed by %.1f (%.1f HP)", packet.health - self.hp, packet.health)
				else:
					self.logger.info("Took %.1f damage (%.1f HP)", self.hp - packet.health, packet.health)
			self.hp = packet.health
			self.food = packet.food + packet.foodSaturation
			if died:
				self.run_callbacks(DeathEvent, DeathEvent())
				self.logger.warning("Died, attempting to respawn")
				await asyncio.sleep(0.5) # TODO make configurable
				await self.dispatcher.write(
					PacketClientCommand(actionId=0) # respawn
				)

		@self.on_packet(PacketExperience)
		async def player_xp_cb(packet:PacketExperience):
			if packet.level != self.lvl:
				self.logger.info("Level up : %d", packet.level)
			self.xp = packet.experienceBar
			self.lvl = packet.level
			self.total_xp = packet.totalExperience

		@self.on_packet(PacketAbilities)
		async def player_abilities_cb(packet:PacketAbilities):
			self.flags = packet.flags
			self.flyingSpeed = packet.flyingSpeed
			self.walkingSpeed = packet.walkingSpeed

