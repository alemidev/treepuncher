from aiocraft.packet import Packet

from .base import BaseEvent

class PacketEvent(BaseEvent):
	packet : Packet
	def __init__(self, p:Packet):
		self.packet = p
