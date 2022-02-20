from typing import Union

from aiocraft.client import MinecraftClient
from aiocraft.mc.proto.play.clientbound import PacketChat as PacketChatMessage
from aiocraft.mc.proto.play.serverbound import PacketChat

from ..events.chat import ChatEvent, MessageType

class GameChat(MinecraftClient):

	def on_chat(self, msg_type:Union[str, MessageType] = None):
		if isinstance(msg_type, str):
			msg_type = MessageType(msg_type)
		def wrapper(fun):
			async def process_chat_packet(packet:PacketChatMessage):
				msg = ChatEvent(packet.message)
				if not msg_type or msg.type == msg_type:
					return await fun(msg)
			self.register(PacketChatMessage, process_chat_packet)
			return fun
		return wrapper


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

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
