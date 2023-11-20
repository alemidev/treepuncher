from typing import List

from aiocraft.types import Item
from aiocraft.proto.play.clientbound import PacketSetSlot, PacketHeldItemSlot as PacketHeldItemChange
from aiocraft.proto.play.serverbound import PacketHeldItemSlot

from ..scaffold import Scaffold

class GameInventory(Scaffold):
	slot : int
	inventory : List[Item]
	# TODO inventory

	async def set_slot(self, slot:int):
		self.slot = slot
		await self.dispatcher.write(PacketHeldItemSlot(slotId=slot))

	@property
	def hotbar(self) -> List[Item]:
		return self.inventory[36:45]

	@property
	def selected(self) -> Item:
		return self.hotbar[self.slot]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.slot = 0
		self.inventory = [ Item() for _ in range(46) ]

		@self.on_packet(PacketSetSlot)
		async def on_set_slot(packet:PacketSetSlot):
			if packet.windowId == 0: # player inventory
				self.inventory[packet.slot] = packet.item

		@self.on_packet(PacketHeldItemChange)
		async def on_held_item_change(packet:PacketHeldItemChange):
			self.slot = packet.slot
