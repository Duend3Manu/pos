import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

usuarios = [
    ("admin", "admin123", "admin"),
    ("cajera", "caja123", "cajera")
]

for u in usuarios:
    cursor.execute(
        "INSERT OR IGNORE INTO usuarios (usuario, password, rol) VALUES (?, ?, ?)",
        u
    )

conn.commit()
conn.close()

print("Usuarios creados correctamente")