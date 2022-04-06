from typing import Type

from aiocraft.client import MinecraftClient
from aiocraft.util import helpers
from aiocraft.mc.packet import Packet
from aiocraft.mc.definitions import ConnectionState
from aiocraft.mc.proto import PacketKickDisconnect, PacketSetCompression
from aiocraft.mc.proto.play.clientbound import PacketKeepAlive
from aiocraft.mc.proto.play.serverbound import PacketKeepAlive as PacketKeepAliveResponse

from .traits import CallbacksHolder, Runnable
from .events import ConnectedEvent, DisconnectedEvent
from .events.base import BaseEvent

class Scaffold(
	MinecraftClient,
	CallbacksHolder,
	Runnable,
):

	def on_packet(self, packet:Type[Packet]):
		def decorator(fun):
			return self.register(packet, fun)
		return decorator

	def on(self, event:Type[BaseEvent]): # TODO maybe move in Treepuncher?
		def decorator(fun):
			return self.register(event, fun)
		return decorator

	#Override
	async def _play(self) -> bool:
		self.dispatcher.state = ConnectionState.PLAY
		self.run_callbacks(ConnectedEvent, ConnectedEvent())
		async for packet in self.dispatcher.packets():
			self._logger.debug("[ * ] Processing %s", packet.__class__.__name__)
			if isinstance(packet, PacketSetCompression):
				self._logger.info("Compression updated")
				self.dispatcher.compression = packet.threshold
			elif isinstance(packet, PacketKeepAlive):
				if self.options.keep_alive:
					keep_alive_packet = PacketKeepAliveResponse(340, keepAliveId=packet.keepAliveId)
					await self.dispatcher.write(keep_alive_packet)
			elif isinstance(packet, PacketKickDisconnect):
				self._logger.error("Kicked while in game : %s", helpers.parse_chat(packet.reason))
				break
			self.run_callbacks(type(packet), packet)
			self.run_callbacks(Packet, packet)
		self.run_callbacks(DisconnectedEvent, DisconnectedEvent())
		return False

