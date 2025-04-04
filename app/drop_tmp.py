import sqlite3
import os

# Constrói o caminho absoluto para o banco de dados
db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'instance', 'debug_adgest.db'))
print("Caminho absoluto do banco de dados:", db_path)
print("O arquivo existe?", os.path.exists(db_path))

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS _alembic_tmp_users;")
    conn.commit()
    conn.close()
    print("Tabela _alembic_tmp_users removida (se existia).")
except Exception as e:
    print("Erro ao conectar ou executar o comando:", e)
