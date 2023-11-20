from aiocraft.proto.play.clientbound import PacketChat as PacketChatMessage
from aiocraft.proto.play.serverbound import PacketChat

from ..events.chat import ChatEvent
from ..scaffold import Scaffold

class GameChat(Scaffold):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		@self.on_packet(PacketChatMessage)
		async def chat_event_callback(packet:PacketChatMessage):
			self.run_callbacks(ChatEvent, ChatEvent(packet.message))

	async def chat(self, message:str, whisper:str="", wait:bool=False):
		if whisper:
			message = f"/w {whisper} {message}"
		await self.dispatcher.write(
			PacketChat(message=message),
			wait=wait
		)

