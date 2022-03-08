from typing import Union

from aiocraft.mc.proto.play.clientbound import PacketChat as PacketChatMessage
from aiocraft.mc.proto.play.serverbound import PacketChat

from ..events.chat import ChatEvent, MessageType
from ..scaffold import Scaffold

class GameChat(Scaffold):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		@self.on_packet(PacketChatMessage)
		async def chat_event_callback(packet:PacketChatMessage):
			self.run_callbacks(ChatEvent, ChatEvent(packet.message))

	async def chat(self, message:str, whisper:str=None, wait:bool=False):
		if whisper:
			message = f"/w {whisper} {message}"
		await self.dispatcher.write(
			PacketChat(
				self.dispatcher.proto,
				message=message
			),
			wait=wait
		)

