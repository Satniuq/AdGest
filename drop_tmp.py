import sqlite3

# Substitua 'database.db' pelo caminho do seu arquivo de banco de dados
db_path = 'caminho/para/seu/database.db'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("DROP TABLE IF EXISTS _alembic_tmp_users;")
conn.commit()
conn.close()

print("Tabela _alembic_tmp_users removida (se existia).")
