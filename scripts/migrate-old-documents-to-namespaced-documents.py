import sqlite3

def migrate_old_documents_to_namespaced_documents(db:str):
	db = sqlite3.connect(db)

	values = db.cursor().execute("SELECT * FROM documents", ()).fetchall();

	for k,v in values:
		if "_" in k:
			addon, key = k.split("_", 1)
			db.cursor().execute("CREATE TABLE IF NOT EXISTS documents_{addon} (name TEXT PRIMARY KEY, value TEXT)", ())
			db.cursor().execute("INSERT INTO documents_{addon} VALUES (?, ?)", (key, v))
			db.cursor().execute("DELETE FROM documents WHERE name = ?", k)

if __name__ == "__main__":
	import sys
	if len(sys.argv) < 2:
		print("[!] No argument given")
		exit(-1)
	migrate_old_documents_to_namespaced_documents(sys.argv[1])

