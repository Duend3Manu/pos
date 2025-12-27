import sqlite3

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn

def migrar_ventas():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Lista de columnas a agregar si faltan
    columnas = [
        ("metodo_pago", "TEXT"),
        ("monto_recibido", "INTEGER"),
        ("vuelto", "INTEGER"),
        ("nombre_transferencia", "TEXT"),
        ("rut_transferencia", "TEXT"),
        ("usuario_id", "INTEGER")
    ]

    for col, tipo in columnas:
        try:
            cursor.execute(f"ALTER TABLE ventas ADD COLUMN {col} {tipo}")
        except sqlite3.OperationalError:
            pass

    # 1️⃣ Normalizar ventas antiguas: Si no tiene método, asumir 'efectivo'
    try:
        cursor.execute("UPDATE ventas SET metodo_pago = 'efectivo' WHERE metodo_pago IS NULL OR metodo_pago = ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def migrar_usuarios():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Intentar renombrar la columna username a usuario si existe (migración)
        cursor.execute("ALTER TABLE usuarios RENAME COLUMN username TO usuario")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def migrar_cierres():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE cierres_caja ADD COLUMN total_ventas INTEGER")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        categoria TEXT,
        precio INTEGER NOT NULL,
        stock INTEGER NOT NULL,
        imagen TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ventas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        total INTEGER NOT NULL,
        metodo_pago TEXT,
        monto_recibido INTEGER,
        vuelto INTEGER,
        nombre_transferencia TEXT,
        rut_transferencia TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS venta_detalle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        venta_id INTEGER,
        producto_id INTEGER,
        cantidad INTEGER,
        precio REAL,
        FOREIGN KEY (venta_id) REFERENCES ventas(id),
        FOREIGN KEY (producto_id) REFERENCES productos(id)
    )
    """)

    # Tabla usuarios
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE,
        password TEXT,
        rol TEXT
    )
    """)

    # Migración por si existía username
    try:
        cursor.execute("ALTER TABLE usuarios RENAME COLUMN username TO usuario")
    except sqlite3.OperationalError:
        pass

    # Usuario admin por defecto
    cursor.execute("""
    INSERT OR IGNORE INTO usuarios (usuario, password, rol)
    VALUES ('admin', '1234', 'admin')
    """)

    # Usuario cajera por defecto
    cursor.execute("""
    INSERT OR IGNORE INTO usuarios (usuario, password, rol)
    VALUES ('cajera', '1234', 'cajera')
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cierres_caja (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        total_ventas INTEGER,
        efectivo_sistema INTEGER,
        tarjeta_sistema INTEGER,
        transferencia_sistema INTEGER,
        efectivo_real INTEGER,
        diferencia INTEGER,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

    # Ejecutar migración para asegurar columnas nuevas
    migrar_ventas()
    migrar_usuarios()
    migrar_cierres()
