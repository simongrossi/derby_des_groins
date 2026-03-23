import sqlite3
import os

db_path = os.path.join('instance', 'derby.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    sql = "UPDATE item SET nom = 'Sérum de Rillettes du Mans' WHERE nom LIKE 'Sérum de Rillettes d%Alençon%'"
    cursor.execute(sql)
    print(f"Rows updated: {cursor.rowcount}")
    conn.commit()
    conn.close()
else:
    print(f"Database not found at {db_path}")
