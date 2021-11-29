from ..treepuncher import Treepuncher, TreepuncherEvents
from .module import LogicModule

from aiocraft.mc.proto.play.clientbound import (
	PacketRespawn, PacketLogin, PacketPosition, PacketUpdateHealth, PacketExperience,
	PacketAbilities, PacketChat as PacketChatMessage
)
from aiocraft.mc.proto.play.serverbound import PacketTeleportConfirm, PacketClientCommand, PacketChat
from aiocraft.mc.definitions import Difficulty, Dimension, Gamemode, Position

class CoreLogic(LogicModule):
	def register(self, client:Treepuncher):
		@client.on_disconnected()
		async def on_disconnected():
			client.in_game = False

		@client.on_packet(PacketRespawn)
		async def on_player_respawning(packet:PacketRespawn):
			client.gamemode = Gamemode(packet.gamemode)
			client.dimension = Dimension(packet.dimension)
			client.difficulty = Difficulty(packet.difficulty)
			if client.difficulty != Difficulty.PEACEFUL \
			and client.gamemode != Gamemode.SPECTATOR:
				client.in_game = True
			else:
				client.in_game = False
			client._logger.info(
				"Reloading world: %s (%s) in %s",
				client.dimension.name,
				client.difficulty.name,
				client.gamemode.name
			)

		@client.on_packet(PacketLogin)
		async def player_joining_cb(packet:PacketLogin):
			client.gamemode = Gamemode(packet.gameMode)
			client.dimension = Dimension(packet.dimension)
			client.difficulty = Difficulty(packet.difficulty)
			if client.difficulty != Difficulty.PEACEFUL \
			and client.gamemode != Gamemode.SPECTATOR:
				client.in_game = True
			else:
				client.in_game = False
			client._logger.info(
				"Joined world: %s (%s) in %s",
				client.dimension.name,
				client.difficulty.name,
				client.gamemode.name
			)
			client.run_callbacks(TreepuncherEvents.IN_GAME)

		@client.on_packet(PacketPosition)
		async def player_rubberband_cb(packet:PacketPosition):
			client._logger.info("Position synchronized")
			client.position = Position(packet.x, packet.y, packet.z)
			await client.dispatcher.write(
				PacketTeleportConfirm(
					client.dispatcher.proto,
					teleportId=packet.teleportId
				)
			)

		@client.on_packet(PacketUpdateHealth)
		async def player_hp_cb(packet:PacketUpdateHealth):
			if packet.health != client.hp and packet.health <= 0:
				client._logger.info("Dead, respawning...")
				await client.dispatcher.write(
					PacketClientCommand(client.dispatcher.proto, actionId=0) # respawn
				)
				client.run_callbacks(TreepuncherEvents.DIED)
			client.hp = packet.health
			client.food = packet.food

		@client.on_packet(PacketExperience)
		async def player_xp_cb(packet:PacketExperience):
			if packet.level != client.lvl:
				client._logger.info("Level up : %d", packet.level)
			client.xp = packet.experienceBar
			client.lvl = packet.level
			client.total_xp = packet.totalExperience

