import re
import logging

from typing import List, Dict, Union, Optional, Any, Type
from enum import Enum

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiocraft.client import MinecraftClient
from aiocraft.mc.packet import Packet
from aiocraft.mc.definitions import Difficulty, Dimension, Gamemode, Position

from aiocraft.mc.proto.play.clientbound import (
	PacketRespawn, PacketLogin, PacketPosition, PacketUpdateHealth, PacketExperience,
	PacketAbilities, PacketChat as PacketChatMessage
)
from aiocraft.mc.proto.play.serverbound import PacketTeleportConfirm, PacketClientCommand, PacketChat

from .events import ChatEvent
from .events.chat import MessageType
from .modules.module import LogicModule

REMOVE_COLOR_FORMATS = re.compile(r"§[0-9a-z]")

class TreepuncherEvents(Enum):
	DIED = 0
	IN_GAME = 1

class Treepuncher(MinecraftClient):
	in_game : bool
	gamemode : Gamemode
	dimension : Dimension
	difficulty : Difficulty

	hp : float
	food : float
	xp : float
	lvl : int
	total_xp : int

	slot : int
	# TODO inventory

	position : Position
	# TODO world

	# TODO player abilities
	# walk_speed : float
	# fly_speed : float
	# flags : int

	scheduler : AsyncIOScheduler
	modules : List[LogicModule]
	ctx : Dict[Any, Any]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.ctx = dict()

		self.in_game = False
		self.gamemode = Gamemode.SURVIVAL
		self.dimension = Dimension.OVERWORLD
		self.difficulty = Difficulty.HARD

		self.hp = 20.0
		self.food = 20.0
		self.xp = 0.0
		self.lvl = 0

		self.slot = 0

		self.position = Position(0, 0, 0)

		self._register_handlers()
		self.modules = []

		self.scheduler = AsyncIOScheduler()
		logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING) # So it's way less spammy
		self.scheduler.start(paused=True)

	async def start(self):
		await super().start()
		self.scheduler.resume()
		for m in self.modules:
			await m.initialize(self)

	async def stop(self, force:bool=False):
		self.scheduler.pause()
		for m in self.modules:
			await m.cleanup(self)
		await super().stop(force=force)

	def add(self, module:LogicModule):
		module.register(self)
		self.modules.append(module)

	def on_chat(self, msg_type:Union[str, MessageType] = None):
		if isinstance(msg_type, str):
			msg_type = MessageType(msg_type)
		def wrapper(fun):
			async def process_chat_packet(packet:PacketChatMessage):
				msg = ChatEvent(packet.message)
				if not msg_type or msg.type == msg_type:
					return await fun(msg)
			return self.register(PacketChatMessage, process_chat_packet)
		return wrapper

	def on_death(self):
		def wrapper(fun):
			return self.register(TreepuncherEvents.DIED, fun)
		return wrapper

	def on_joined_world(self):
		def wrapper(fun):
			return self.register(TreepuncherEvents.IN_GAME, fun)
		return wrapper

	async def write(self, packet:Packet, wait:bool=False):
		await self.dispatcher.write(packet, wait)

	async def chat(self, message:str, wait:bool=False):
		await self.dispatcher.write(
			PacketChat(
				self.dispatcher.proto,
				message=message
			),
			wait=wait
		)

	def _register_handlers(self):
		@self.on_disconnected()
		async def on_disconnected():
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
			self.run_callbacks(TreepuncherEvents.IN_GAME)

		@self.on_packet(PacketPosition)
		async def player_rubberband_cb(packet:PacketPosition):
			self._logger.info("Position synchronized")
			self.position = Position(packet.x, packet.y, packet.z)
			await self.dispatcher.write(
				PacketTeleportConfirm(
					self.dispatcher.proto,
					teleportId=packet.teleportId
				)
			)

		@self.on_packet(PacketUpdateHealth)
		async def player_hp_cb(packet:PacketUpdateHealth):
			if packet.health != self.hp and packet.health <= 0:
				self._logger.info("Dead, respawning...")
				await self.dispatcher.write(
					PacketClientCommand(self.dispatcher.proto, actionId=0) # respawn
				)
				self.run_callbacks(TreepuncherEvents.DIED)
			self.hp = packet.health
			self.food = packet.food

		@self.on_packet(PacketExperience)
		async def player_hp_cb(packet:PacketExperience):
			if packet.level != self.lvl:
				self._logger.info("Level up : %d", packet.level)
			self.xp = packet.experienceBar
			self.lvl = packet.level
			self.total_xp = packet.totalExperience

