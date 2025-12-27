from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from database import init_db, get_db_connection
from datetime import datetime, date
from auth import solo_admin

app = Flask(__name__)
app.secret_key = "pos_dulce_caramelo_2025"

# Configuración de dinero (Chile)
BILLETES = [20000, 10000, 5000, 2000, 1000]
MONEDAS = [500, 100, 50, 10]

# Inicializar base de datos
init_db()

# Utilidad para redondeo CLP
def clp(valor):
    if valor is None:
        return 0
    try:
        return int(round(float(valor)))
    except (ValueError, TypeError):
        return 0

@app.template_filter('clp')
def format_clp(value):
    return "{:,}".format(clp(value)).replace(",", ".")

@app.route("/")
def home():
    return redirect(url_for("ventas"))


@app.route("/productos")
def productos():
    conn = get_db_connection()
    productos = conn.execute("SELECT * FROM productos").fetchall()
    conn.close()
    return render_template("productos.html", productos=productos)


@app.route("/productos/nuevo", methods=["POST"])
def nuevo_producto():
    nombre = request.form["nombre"]
    categoria = request.form["categoria"]
    precio = request.form["precio"]
    stock = request.form["stock"]

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO productos (nombre, categoria, precio, stock) VALUES (?, ?, ?, ?)",
        (nombre, categoria, precio, stock)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("productos"))


@app.route("/ventas")
def ventas():
    conn = get_db_connection()
    productos = conn.execute("SELECT * FROM productos").fetchall()
    conn.close()

    return render_template("ventas_pos.html", productos=productos)


@app.route("/agregar_producto", methods=["POST"])
def agregar_producto():
    producto_id = request.form["producto_id"]
    cantidad = int(request.form["cantidad"])

    conn = get_db_connection()
    producto = conn.execute("SELECT * FROM productos WHERE id = ?", (producto_id,)).fetchone()
    conn.close()

    if producto:
        carrito = session.get("carrito", [])
        
        # Verificar si el producto ya está en el carrito
        for item in carrito:
            if item["id"] == producto_id:
                item["cantidad"] += cantidad
                item["total"] = clp(item["cantidad"] * item["precio"])
                session["carrito"] = carrito
                return redirect(url_for("ventas"))

        # Si no está, agregarlo
        carrito.append({
            "id": producto_id,
            "nombre": producto["nombre"],
            "precio": producto["precio"],
            "cantidad": cantidad,
            "total": clp(producto["precio"] * cantidad)
        })
        session["carrito"] = carrito

    return redirect(url_for("ventas"))


@app.route("/procesar_carrito", methods=["POST"])
def procesar_carrito():
    data = request.get_json()
    session["carrito_pos"] = data.get("items", [])
    session["total_pos"] = data.get("total", 0)
    return jsonify({"status": "ok"})


@app.route("/cobro", methods=["GET", "POST"])
def cobro():
    total = clp(session.get("total_pos", 0))
    carrito = session.get("carrito", [])
    # Si usamos el POS visual, el carrito puede venir de session["carrito_pos"]
    # pero para simplificar, asumiremos que la lógica de backend usa session["carrito"]
    # o adaptamos según lo que envíe el frontend.
    # En este paso, usaremos el total calculado.

    if request.method == "POST":
        # 2️⃣ Blindar el sistema: Si no llega método, asumir 'efectivo'
        metodo = request.form.get("metodo")
        if not metodo:
            metodo = "efectivo"

        monto = request.form.get("monto_recibido")
        nombre = request.form.get("nombre_transfiere")
        rut = request.form.get("rut_transfiere")
        usuario_id = session.get("user_id")

        vuelto = 0
        if metodo == "efectivo":
            monto = clp(monto)
            vuelto = monto - total
        else:
            monto = 0 # Opcional: guardar 0 o NULL si no es efectivo

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Crear Venta
        cursor.execute("""
            INSERT INTO ventas (fecha, total, metodo_pago, monto_recibido, vuelto, nombre_transferencia, rut_transferencia, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            total,
            metodo,
            monto,
            vuelto,
            nombre,
            rut,
            usuario_id
        ))
        
        # Aquí deberíamos guardar el detalle de venta_detalle iterando sobre los items
        # (pendiente de conectar items del frontend con backend en este paso)

        conn.commit()
        conn.close()

        return redirect(url_for("ventas"))

    return render_template("cobro.html", total=total)


@app.route("/cancelar_venta")
def cancelar_venta():
    session.pop("carrito", None)
    return redirect(url_for("ventas"))


@app.route("/reportes/diario")
def reporte_diario():
    if "usuario" not in session:
        return redirect(url_for("login"))
        
    conn = get_db_connection()
    
    # REPORTE DIARIO
    hoy = datetime.now().strftime("%Y-%m-%d")

    diario = conn.execute("""
        SELECT metodo_pago, SUM(total) as total
        FROM ventas
        WHERE fecha LIKE ?
        GROUP BY metodo_pago
    """, (hoy + "%",)).fetchall()

    conn.close()

    return render_template(
        "reporte_diario.html",
        diario=diario,
        hoy=hoy
    )

@app.route("/reportes/mensual")
@solo_admin
def reporte_mensual():
    conn = get_db_connection()
    
    # REPORTE MENSUAL
    mes = datetime.now().strftime("%Y-%m")

    mensual = conn.execute("""
        SELECT metodo_pago, SUM(total) as total
        FROM ventas
        WHERE fecha LIKE ?
        GROUP BY metodo_pago
    """, (mes + "%",)).fetchall()

    conn.close()

    return render_template(
        "reporte_mensual.html",
        mensual=mensual,
        mes=mes
    )


@app.route("/cierre_caja", methods=["GET", "POST"])
def cierre_caja():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Nota: Quitamos la restricción de solo admin. 
    # Ahora la cajera puede cerrar SU turno (se filtra por usuario_id).

    hoy = date.today().strftime("%Y-%m-%d")
    conn = get_db_connection()
    uid = session["user_id"]

    # Totales del sistema por método de pago para el día de hoy
    efectivo = clp(conn.execute("SELECT COALESCE(SUM(total),0) FROM ventas WHERE usuario_id=? AND metodo_pago='efectivo' AND fecha LIKE ?", (uid, hoy + "%")).fetchone()[0])
    tarjeta = clp(conn.execute("SELECT COALESCE(SUM(total),0) FROM ventas WHERE usuario_id=? AND metodo_pago='tarjeta' AND fecha LIKE ?", (uid, hoy + "%")).fetchone()[0])
    transferencia = clp(conn.execute("SELECT COALESCE(SUM(total),0) FROM ventas WHERE usuario_id=? AND metodo_pago='transferencia' AND fecha LIKE ?", (uid, hoy + "%")).fetchone()[0])
    
    total_ventas = efectivo + tarjeta + transferencia

    if request.method == "POST":
        # Calcular efectivo real basado en billetes y monedas
        efectivo_contado = 0
        
        for b in BILLETES:
            cantidad = int(request.form.get(f"b_{b}", 0))
            efectivo_contado += cantidad * b
            
        for m in MONEDAS:
            cantidad = int(request.form.get(f"m_{m}", 0))
            efectivo_contado += cantidad * m

        diferencia = efectivo_contado - efectivo

        conn.execute("""
            INSERT INTO cierres_caja (usuario_id, total_ventas, efectivo_sistema, tarjeta_sistema, transferencia_sistema, efectivo_real, diferencia, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, total_ventas, efectivo, tarjeta, transferencia, efectivo_contado, diferencia, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        conn.commit()
        conn.close()
        return redirect(url_for("historial_cierres"))

    conn.close()

    return render_template(
        "cierre_caja.html",
        efectivo=efectivo,
        tarjeta=tarjeta,
        transferencia=transferencia,
        total=total_ventas,
        billetes=BILLETES,
        monedas=MONEDAS
    )


@app.route("/historial_cierres")
def historial_cierres():
    conn = get_db_connection()
    cierres = conn.execute("""
        SELECT c.fecha, u.usuario,
               c.total_ventas,
               c.efectivo_sistema,
               c.tarjeta_sistema,
               c.transferencia_sistema,
               c.efectivo_real,
               c.diferencia
        FROM cierres_caja c
        JOIN usuarios u ON u.id = c.usuario_id
        ORDER BY c.fecha DESC
    """).fetchall()
    conn.close()

    return render_template("historial_cierres.html", cierres=cierres)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        password = request.form.get("password")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE usuario = ? AND password = ?",
            (usuario, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["usuario"] = user["usuario"]
            session["rol"] = user["rol"]
            return redirect("/")
        else:
            return render_template("login.html", error="Usuario o contraseña incorrecta")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route('/usuarios', methods=['GET', 'POST'])
@solo_admin
def usuarios():
    conn = get_db_connection()
    
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        rol = request.form['rol']

        try:
            conn.execute("""
            INSERT INTO usuarios (usuario, password, rol)
            VALUES (?, ?, ?)
            """, (usuario, password, rol))
            conn.commit()
        except:
            # Si el usuario ya existe, podríamos manejar el error aquí
            pass

    usuarios = conn.execute("SELECT * FROM usuarios").fetchall()
    conn.close()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/usuarios/reset/<int:id>')
@solo_admin
def reset_pass(id):
    conn = get_db_connection()
    conn.execute("""
    UPDATE usuarios SET password = '1234' WHERE id = ?
    """, (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('usuarios'))

if __name__ == "__main__":
    app.run(debug=True)
