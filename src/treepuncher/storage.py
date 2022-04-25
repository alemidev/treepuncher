import os
import json
import sqlite3

from dataclasses import dataclass
from typing import Optional, Any, Dict
from datetime import datetime

__DATE_FORMAT__ : str = "%Y-%m-%d %H:%M:%S.%f"

@dataclass
class SystemState:
	name : str
	version : str
	start_time : int

@dataclass
class AuthenticatorState:
	date : datetime
	token : Dict[str, Any]
	legacy : bool = False

class Storage:
	name : str
	db : sqlite3.Connection


	def __init__(self, name:str):
		self.name = name
		init = not os.path.isfile(f"{name}.session")
		self.db = sqlite3.connect(f'{name}.session')
		if init:
			self._init_db()

	def __del__(self):
		self.close()

	def close(self) -> None:
		self.db.close()

	def _init_db(self):
		cur = self.db.cursor()
		cur.execute('CREATE TABLE system (name TEXT PRIMARY KEY, version TEXT, start_time LONG)')
		cur.execute('CREATE TABLE documents (name TEXT PRIMARY KEY, value TEXT)')
		cur.execute('CREATE TABLE authenticator (date TEXT PRIMARY KEY, token TEXT, legacy BOOL)')
		self.db.commit()

	def _set_state(self, state:SystemState):
		cur = self.db.cursor()
		cur.execute('DELETE FROM system')
		cur.execute('INSERT INTO system VALUES (?, ?, ?)', (state.name, state.version, int(state.start_time)))
		self.db.commit()

	def _set_auth(self, state:AuthenticatorState):
		cur = self.db.cursor()
		cur.execute('DELETE FROM authenticator')
		cur.execute('INSERT INTO authenticator VALUES (?, ?, ?)', (state.date.strftime(__DATE_FORMAT__), json.dumps(state.token), state.legacy))
		self.db.commit()

	def system(self) -> Optional[SystemState]:
		cur = self.db.cursor()
		val = cur.execute('SELECT * FROM system').fetchall()
		if not val:
			return None
		return SystemState(
			name=val[0][0],
			version=val[0][1],
			start_time=val[0][2]
		)

	def auth(self) -> Optional[AuthenticatorState]:
		cur = self.db.cursor()
		val = cur.execute('SELECT * FROM authenticator').fetchall()
		if not val:
			return None
		return AuthenticatorState(
			date=datetime.strptime(val[0][0], __DATE_FORMAT__),
			token=json.loads(val[0][1]),
			legacy=val[0][2] or False
		)

	def get(self, key:str) -> Optional[Any]:
		cur = self.db.cursor()
		val = cur.execute("SELECT * FROM documents WHERE name = ?", (key,)).fetchall()
		return json.loads(val[0][1]) if val else None

	def put(self, key:str, val:Any) -> None:
		cur = self.db.cursor()
		cur.execute("DELETE FROM documents WHERE name = ?", (key,))
		cur.execute("INSERT INTO documents VALUES (?, ?)", (key, json.dumps(val, default=str)))
		self.db.commit()

