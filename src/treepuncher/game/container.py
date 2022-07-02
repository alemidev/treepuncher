import asyncio
import datetime
from typing import List, Optional

#from aiocraft.client import MinecraftClient
from aiocraft.mc.definitions import Item
from aiocraft.mc.proto import (
	PacketOpenWindow, PacketCloseWindow, PacketSetSlot
)

from ..events import JoinGameEvent, DeathEvent, ConnectedEvent, DisconnectedEvent
from ..scaffold import Scaffold

class GameContainer(Scaffold):
	window_id : int
	window_title : str
	window_inventory_type : str
	window_entity_id : Optional[int]
	window_transaction_id : int
	window_inventory : List[Item]

	@property
	def is_container_open(self) -> bool:
		return self.window_id > 0

	@property
	def next_window_tid(self) -> int:
		self.window_transaction_id += 1
		return self.window_transaction_id

	async def close_container(self):
		await self.dispatcher.write(
			PacketCloseWindow(
				self.dispatcher.proto,
				windowId=self.window_id
			)
		)
		self.window_transaction_id = 0
		self.window_id = -1
		self.window_title = ""

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.window_transaction_id = 0
		self.window_id = -1
		self.window_title = ""
		self.window_inventory_type = ""
		self.window_entity_id = None
		self.window_inventory = []

		@self.on(DisconnectedEvent)
		async def disconnected_cb(_):
			self.window_transaction_id = 0
			self.window_id = -1
			self.window_title = ""

		@self.on_packet(PacketOpenWindow)
		async def on_player_open_window(packet:PacketOpenWindow):
			self.window_id = packet.windowId
			self.window_title = packet.windowTitle
			self.window_inventory_type = packet.inventoryType
			self.window_entity_id = packet.entityId
			self.window_inventory = [None] * packet.slotCount

		@self.on_packet(PacketSetSlot)
		async def on_set_slot(packet:PacketSetSlot):
			if packet.windowId == self.window_id:
				self.window_inventory[packet.slot] = packet.item
