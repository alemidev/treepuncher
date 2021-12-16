import re

from typing import Optional
from enum import Enum

from aiocraft.util.helpers import parse_chat

CHAT_MESSAGE_MATCHER = re.compile(r"<(?P<usr>[A-Za-z0-9_]+)> (?P<msg>.+)")
REMOVE_COLOR_FORMATS = re.compile(r"§[0-9a-z]")
WHISPER_MATCHER = re.compile(r"(?:to (?P<touser>[A-Za-z0-9_]+)( |):|(?P<fromuser>[A-Za-z0-9_]+) whispers( |):|from (?P<from9b>[A-Za-z0-9_]+):) (?P<txt>.+)", flags=re.IGNORECASE)
JOIN_LEAVE_MATCHER = re.compile(r"(?P<usr>[A-Za-z0-9_]+) (?P<action>joined|left)( the game|)$", flags=re.IGNORECASE)

class MessageType(Enum):
	CHAT = "chat"
	WHISPER = "whisper"
	#COMMAND = "cmd"
	#DEATH = "death" # ???? TODO!
	JOIN = "join"
	LEAVE = "leave"
	SYSTEM = "system"

class ChatEvent:
	text : str
	type : MessageType
	user : str
	target : str
	message : str

	def __init__(self, text:str):
		self.text = REMOVE_COLOR_FORMATS.sub("", parse_chat(text))
		self.user = ""
		self.target = ""
		self.message= ""
		self.type = MessageType.SYSTEM
		self._parse()

	def _parse(self):
		match = CHAT_MESSAGE_MATCHER.search(self.text)
		if match:
			self.type = MessageType.CHAT
			self.user = match["usr"]
			self.message = match["msg"]
			return

		match = WHISPER_MATCHER.search(self.text)
		if match:
			self.type = MessageType.WHISPER
			self.user = match["fromuser"] or match["from9b"]
			self.target = match["touser"]
			self.message = match["txt"]
			return

		match = JOIN_LEAVE_MATCHER.search(self.text)
		if match:
			self.type = MessageType.JOIN if match["action"] == "join" else MessageType.LEAVE
			self.user = match["usr"]
			return
