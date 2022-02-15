import uuid
import datetime

from typing import Dict, List

from aiocraft.client import MinecraftClient
from aiocraft.mc.definitions import Item
from aiocraft.mc.proto import PacketPlayerInfo

class GameTablist(MinecraftClient):
	tablist : Dict[uuid.UUID, dict]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.tablist = {}

		@self.on_connected()
		async def connected_cb():
			self.tablist.clear()

		@self.on_packet(PacketPlayerInfo)
		async def tablist_update(packet:PacketPlayerInfo):
			for record in packet.data:
				uid = record['UUID']
				if packet.action != 0 and uid not in self.tablist:
					continue # TODO this happens kinda often but doesn't seem to be an issue?
				if packet.action == 0:
					self.tablist[uid] = record
					self.tablist[uid]['joinTime'] = datetime.datetime.now()
				elif packet.action == 1:
					self.tablist[uid]['gamemode'] = record['gamemode']
				elif packet.action == 2:
					self.tablist[uid]['ping'] = record['ping']
				elif packet.action == 3:
					self.tablist[uid]['displayName'] = record['displayName']
				elif packet.action == 4:
					self.tablist.pop(uid, None)



