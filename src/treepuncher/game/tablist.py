import uuid
import datetime

from enum import Enum
from typing import Dict, List

from aiocraft.mc.definitions import Player
from aiocraft.mc.proto import PacketPlayerInfo

from ..scaffold import Scaffold
from ..events import ConnectedEvent, PlayerJoinEvent, PlayerLeaveEvent

class ActionType(Enum): # TODO move this in aiocraft
	ADD_PLAYER = 0
	UPDATE_GAMEMODE = 1
	UPDATE_LATENCY = 2
	UPDATE_DISPLAY_NAME = 3
	REMOVE_PLAYER = 4

class GameTablist(Scaffold):
	tablist : Dict[uuid.UUID, Player]

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.tablist = {}

		@self.on(ConnectedEvent)
		async def connected_cb(_):
			self.tablist.clear()

		@self.on_packet(PacketPlayerInfo)
		async def tablist_update(packet:PacketPlayerInfo):
			for record in packet.data:
				uid = record['UUID']
				if packet.action != ActionType.ADD_PLAYER.value and uid not in self.tablist:
					continue # TODO this happens kinda often but doesn't seem to be an issue?
				if packet.action == ActionType.ADD_PLAYER.value:
					record['joinTime'] = datetime.datetime.now()
					self.tablist[uid] = Player.deserialize(record) # TODO have it be a Player type inside packet
					self.run_callbacks(PlayerJoinEvent, PlayerJoinEvent(Player.deserialize(record)))
				elif packet.action == ActionType.UPDATE_GAMEMODE.value:
					self.tablist[uid].gamemode = record['gamemode']
				elif packet.action == ActionType.UPDATE_LATENCY.value:
					self.tablist[uid].ping = record['ping']
				elif packet.action == ActionType.UPDATE_DISPLAY_NAME.value:
					self.tablist[uid].displayName = record['displayName']
				elif packet.action == ActionType.REMOVE_PLAYER.value:
					self.tablist.pop(uid, None)
					self.run_callbacks(PlayerLeaveEvent, PlayerLeaveEvent(Player.deserialize(record)))



