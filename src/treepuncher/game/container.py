from aiocraft.types import Item
from aiocraft.proto.play.clientbound import PacketTransaction
from aiocraft.proto.play.serverbound import PacketTransaction as PacketTransactionServerbound
from aiocraft.proto import (
	PacketOpenWindow, PacketCloseWindow, PacketSetSlot
)

from ..events import DisconnectedEvent
from ..scaffold import Scaffold

class WindowContainer:
	id: int
	title: str
	type: str
	entity_id: int | None
	transaction_id: int
	inventory: list[Item | None]

	def __init__(self, id:int, title: str, type: str, entity_id:int | None = None, slot_count:int = 27):
		self.id = id
		self.title = title
		self.type = type
		self.entity_id = entity_id
		self.transaction_id = 0
		self.inventory = [ None ] * (slot_count + 36)

	@property
	def next_tid(self) -> int:
		self.transaction_id += 1
		if self.transaction_id > 32767:
			self.transaction_id = -32768  # force short overflow since this is sent over the socket as a short
		return self.transaction_id

class GameContainer(Scaffold):
	window: WindowContainer | None

	@property
	def is_container_open(self) -> bool:
		return self.window is not None

	async def close_container(self):
		await self.dispatcher.write(
			PacketCloseWindow(
				self.dispatcher.proto,
				windowId=self.window.id
			)
		)
		self.window = None

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.window = None

		@self.on(DisconnectedEvent)
		async def disconnected_cb(_):
			self.window = None

		@self.on_packet(PacketOpenWindow)
		async def on_player_open_window(packet:PacketOpenWindow):
			assert isinstance(packet.inventoryType, str)
			window_entity_id = packet.entityId if packet.inventoryType == "EntityHorse" and hasattr(packet, "entityId") else None
			self.window = WindowContainer(
				packet.windowId,
				packet.windowTitle,
				packet.inventoryType,
				entity_id=window_entity_id,
				slot_count=packet.slotCount or 27
			)

		@self.on_packet(PacketSetSlot)
		async def on_set_slot(packet:PacketSetSlot):
			if packet.windowId == 0:
				self.window = None
			elif self.window and packet.windowId == self.window.id:
				self.window.inventory[packet.slot] = packet.item

		@self.on_packet(PacketTransaction)
		async def on_transaction_denied(packet:PacketTransaction):
			if self.window and packet.windowId == self.window.id:
				if not packet.accepted:  # apologize to server automatically
					await self.dispatcher.write(
						PacketTransactionServerbound(
							windowId=packet.windowId,
							action=packet.action,
							accepted=packet.accepted,
						)
					)
