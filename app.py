import os
import secrets
import threading
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from flask import Flask, request, redirect, url_for, flash, get_flashed_messages, session
import mysql.connector
from mysql.connector import pooling, errors
import html
from auth import PERFILES, autenticar, inicio_actual, perfil_actual, registrar_control_acceso, rol_actual

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FERRETERIA_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("FERRETERIA_HTTPS", "0") == "1",
)

# =====================================
# POOL DE CONEXIONES A MYSQL (LAZY)
# =====================================

_pool_lock = threading.Lock()
db_pool = None


def _obtener_config_mysql():
    return {
        "host": (
            os.environ.get("MYSQL_ADDON_HOST")
            or os.environ.get("MYSQLHOST")
            or os.environ.get("MYSQL_HOST")
            or "bqshk0tmkut51l0b7443-mysql.services.clever-cloud.com"
        ),
        "port": int(
            os.environ.get("MYSQL_ADDON_PORT")
            or os.environ.get("MYSQLPORT")
            or os.environ.get("MYSQL_PORT")
            or 3306
        ),
        "user": (
            os.environ.get("MYSQL_ADDON_USER")
            or os.environ.get("MYSQLUSER")
            or os.environ.get("MYSQL_USER")
            or "u29kmphcoi5dtsu0"
        ),
        "password": (
            os.environ.get("MYSQL_ADDON_PASSWORD")
            or os.environ.get("MYSQLPASSWORD")
            or os.environ.get("MYSQL_PASSWORD")
            or "pA3Hzhcrn2yJ1U8FUkXw"
        ),
        "database": (
            os.environ.get("MYSQL_ADDON_DB")
            or os.environ.get("MYSQLDATABASE")
            or os.environ.get("MYSQL_DATABASE")
            or "bqshk0tmkut51l0b7443"
        ),
        "connect_timeout": 10,
    }


def _crear_pool():
    cfg = _obtener_config_mysql()
    pid = os.getpid()
    pool_nombre = f"ferreteria_pool_{pid}"
    return pooling.MySQLConnectionPool(
        pool_name=pool_nombre,
        pool_size=2,
        pool_reset_session=True,
        **cfg
    )


def obtener_pool():
    global db_pool
    if db_pool is None:
        with _pool_lock:
            if db_pool is None:
                db_pool = _crear_pool()
    return db_pool


def obtener_conexion():
    global db_pool
    for intento in range(2):
        try:
            pool = obtener_pool()
            conexion = pool.get_connection()
            if conexion.is_connected():
                return conexion
            conexion.reconnect(attempts=2, delay=1)
            return conexion
        except Exception as error:
            print(f"Reintentando conexión con MySQL (intento {intento + 1}): {error}")
            with _pool_lock:
                db_pool = None
            if intento == 1:
                cfg = _obtener_config_mysql()
                return mysql.connector.connect(**cfg)


# =====================================
# REGISTRO DE BLUEPRINTS
# =====================================

from proveedores import proveedores_bp

app.register_blueprint(proveedores_bp)


# =====================================
# PLANTILLA BASE Y ESTILOS
# =====================================

def render_layout(titulo, contenido, seccion_activa=""):
    """
    Layout maestro profesional con tema moderno, tipografía Inter,
    Bootstrap 5.3.3, Bootstrap Icons y paleta de colores optimizada.
    """
    flashed = get_flashed_messages(with_categories=True)
    alertas_html = ""
    for cat, msg in flashed:
        icono = "bi-check-circle-fill" if cat == "success" else ("bi-exclamation-triangle-fill" if cat in ["warning", "danger"] else "bi-info-circle-fill")
        alertas_html += f"""
        <div class="alert alert-{cat} alert-dismissible fade show d-flex align-items-center shadow-sm border-0 mb-4" role="alert">
            <i class="bi {icono} fs-5 me-2"></i>
            <div>{html.escape(msg)}</div>
            <button type="button" class="btn-close ms-auto" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
        """

    def active_class(seccion):
        return "active fw-bold text-white bg-primary bg-opacity-75" if seccion_activa == seccion else "text-light"

    rol = rol_actual()
    perfil = perfil_actual()
    enlaces = []
    if rol in {"ADMIN", "ADMINISTRACION"}:
        enlaces = [
            ("inicio", "/", "bi-grid-1x2-fill", "Panel"),
            ("productos", "/productos", "bi-box-seam-fill", "Productos"),
            ("ventas", "/ventas/", "bi-cart-check-fill", "Ventas"),
            ("cheques", "/cheques/", "bi-bank", "Cheques"),
            ("clientes", "/clientes", "bi-people-fill", "Clientes"),
            ("cuenta_corriente", "/cuenta-corriente", "bi-credit-card-2-front-fill", "Cuenta corriente"),
            ("ferreteria_ia", "/ferreteria-ia", "bi-chat-dots-fill", "FerreterIA"),
            ("proveedores", "/proveedores", "bi-truck", "Proveedores"),
            ("alertas", "/alertas", "bi-exclamation-triangle-fill", "Alertas"),
            ("analisis", "/analisis/", "bi-graph-up-arrow", "Análisis de datos"),
        ]
    elif rol == "DEPOSITO":
        enlaces = [("productos", "/productos", "bi-box-seam-fill", "Stock y productos")]
    elif rol == "VENDEDOR":
        enlaces = [("productos", "/productos", "bi-box-seam-fill", "Stock"), ("ventas", "/ventas/", "bi-cart-check-fill", "Ventas")]

    nav_links = "".join(
        f'<li class="nav-item"><a class="nav-link {active_class(seccion)}" href="{href}">'
        f'<i class="bi {icono}"></i> {etiqueta}</a></li>'
        for seccion, href, icono, etiqueta in enlaces
    )
    identidad_html = ""
    if session.get("id_usuario"):
        identidad_html = f"""
        <div class="d-flex align-items-center gap-2 text-light small">
            <span>{html.escape(str(session.get('nombre_usuario', '')))} · {html.escape(perfil.get('nombre', 'Usuario'))}</span>
            <form method="post" action="/logout" class="m-0">
                <button class="btn btn-sm btn-outline-light" type="submit"><i class="bi bi-box-arrow-right"></i> Salir</button>
            </form>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(titulo)} - Ferretería CANJER</title>
    <!-- Google Fonts & Bootstrap 5.3.3 & Bootstrap Icons -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <style>
        :root {{
            --font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
            --brand-primary: #1e3a8a;
            --brand-accent: #3b82f6;
            --surface-bg: #f8fafc;
        }}
        body {{
            font-family: var(--font-family);
            background-color: var(--surface-bg);
            color: #1e293b;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        .navbar-brand {{
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .nav-link {{
            border-radius: 8px;
            padding: 0.5rem 0.9rem !important;
            transition: all 0.2s ease;
        }}
        .nav-link:hover {{
            background-color: rgba(255, 255, 255, 0.15);
            color: #ffffff !important;
        }}
        .card {{
            border-radius: 14px;
            border: 1px solid rgba(226, 232, 240, 0.9);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }}
        .table-card {{
        }}
        .table thead th {{
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-weight: 700;
            color: #64748b;
            background-color: #f1f5f9;
            border-bottom: 1px solid #cbd5e1;
            padding-top: 0.85rem;
            padding-bottom: 0.85rem;
        }}
        .table tbody td {{
            padding: 0.85rem 1rem;
            vertical-align: middle;
            color: #334155;
            font-size: 0.92rem;
        }}
        .btn {{
            font-weight: 600;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            transition: all 0.18s ease-in-out;
        }}
        .btn:hover {{
            transform: translateY(-1px);
        }}
        .badge {{
            font-weight: 600;
            letter-spacing: 0.02em;
            padding: 0.4em 0.7em;
            border-radius: 6px;
        }}
        .metric-card {{
            border: none;
            border-left: 4px solid var(--brand-accent);
        }}
        .metric-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08);
        }}
        footer {{
            margin-top: auto;
            border-top: 1px solid #e2e8f0;
            background: #ffffff;
        }}
    </style>
</head>
<body>
    <!-- BARRA DE NAVEGACIÓN SUPERIOR -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark py-2 shadow-sm sticky-top" style="background-color: #0f172a !important;">
        <div class="container-fluid px-lg-4">
            <a class="navbar-brand text-white d-flex align-items-center gap-2" href="/">
                <span class="fs-4">🔨</span>
                <span>Ferretería <span class="text-primary-emphasis fw-bolder">CANJER</span></span>
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu" aria-controls="navMenu" aria-expanded="false" aria-label="Navegación">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navMenu">
                <ul class="navbar-nav me-auto mb-2 mb-lg-0 gap-1 ms-lg-3">{nav_links}</ul>
                {identidad_html}
            </div>
        </div>
    </nav>

    <!-- CONTENEDOR PRINCIPAL -->
    <main class="container-fluid px-lg-4 py-4 flex-grow-1">
        {alertas_html}
        {contenido}
    </main>

    <!-- FOOTER -->
    <footer class="py-3 text-center text-muted small">
        <div class="container-fluid">
            <span>© 2026 <strong>Ferretería CANJER</strong> &bull; Sistema Integral de Gestión v2.0</span>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Búsqueda en tiempo real universal para tablas
        function inicializarBuscador(inputId, tableId) {{
            const input = document.getElementById(inputId);
            const table = document.getElementById(tableId);
            if (!input || !table) return;

            input.addEventListener('keyup', function() {{
                const filter = this.value.toLowerCase().trim();
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {{
                    const text = row.textContent.toLowerCase();
                    row.style.display = text.includes(filter) ? '' : 'none';
                }});
            }});
        }}
    </script>
</body>
</html>
"""


# =====================================
# REGISTRO DEL MÓDULO DE VENTAS
# =====================================

from ventas import ventas_bp
from cheques import cheques_bp
from analisis import analisis_bp

app.register_blueprint(ventas_bp)
app.register_blueprint(cheques_bp)
app.register_blueprint(analisis_bp)
registrar_control_acceso(app)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("id_usuario"):
        return redirect(url_for(inicio_actual()))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            usuario = autenticar(username, password)
        except Exception as error:
            print(f"No se pudo consultar el usuario durante el login: {type(error).__name__}")
            flash("La base de datos no está disponible para verificar el acceso. Inténtalo nuevamente.", "danger")
            return redirect(url_for("login"))

        if not usuario:
            flash("Usuario o contraseña incorrectos, o cuenta inactiva.", "danger")
            return redirect(url_for("login"))

        session.clear()
        session.update({
            "id_usuario": usuario["id_usuario"],
            "id_empleado": usuario["id_empleado"],
            "username": usuario["username"],
            "nombre_usuario": usuario["nombre"],
            "rol": usuario["rol"],
        })
        return redirect(url_for(inicio_actual()))

    mensajes_login = "".join(
        f'<div class="alert alert-{html.escape(categoria)}" role="alert">{html.escape(mensaje)}</div>'
        for categoria, mensaje in get_flashed_messages(with_categories=True)
    )
    return f"""<!DOCTYPE html>
    <html lang="es"><head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Ingresar - Ferretería CANJER</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head><body class="bg-light">
        <main class="container min-vh-100 d-flex align-items-center justify-content-center py-4">
            <section class="card border-0 shadow-sm" style="width: min(100%, 960px);">
                <div class="card-body p-4 p-md-5">
                    <div class="row justify-content-center">
                        <div class="col-lg-6">
                            <h1 class="h3 fw-bold mb-1">Ferretería CANJER</h1>
                            <p class="text-muted mb-4">Inicia sesión para continuar</p>
                            {mensajes_login}
                            <form method="post" action="/login">
                                <div class="mb-3"><label class="form-label" for="username">Usuario</label>
                                    <input class="form-control" id="username" name="username" autocomplete="username" required autofocus>
                                </div>
                                <div class="mb-4"><label class="form-label" for="password">Contraseña</label>
                                    <input class="form-control" id="password" name="password" type="password" autocomplete="current-password" required>
                                </div>
                                <button class="btn btn-primary w-100" type="submit">Ingresar</button>
                            </form>
                        </div>
                    </div>
                </div>
            </section>
        </main>
    </body></html>"""


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/ferreteria-ia", methods=["GET", "POST"])
def ferreteria_ia():
    historial = session.get("ferreteria_ia_historial", [])
    error_chat = None

    if request.method == "POST":
        pregunta = request.form.get("pregunta", "").strip()
        if not pregunta:
            error_chat = "Escribe una pregunta para consultar."
        elif len(pregunta) > 500:
            error_chat = "La pregunta no puede superar los 500 caracteres."
        else:
            try:
                from chatbot.ferreteria import responder_con_sql

                sql, respuesta = responder_con_sql(pregunta)
                historial.append({
                    "pregunta": pregunta,
                    "respuesta": str(respuesta)[:2000],
                    "sql": str(sql)[:4000],
                })
                historial = historial[-5:]
                session["ferreteria_ia_historial"] = historial
            except Exception as error:
                print(f"Error en consulta FerreterIA: {type(error).__name__}")
                mensaje_error = str(error)
                if "GROQ_API_KEY" in mensaje_error:
                    error_chat = "Falta GROQ_API_KEY. Agrégala al archivo .env y reinicia la aplicación."
                elif "MYSQL" in mensaje_error:
                    error_chat = "Faltan variables de conexión MySQL en .env; completa MYSQL_ADDON_HOST, USER, PASSWORD y DB."
                elif "Groq" in mensaje_error:
                    error_chat = "Groq no pudo generar el SQL. Verifica GROQ_MODEL, tu cuota y el estado de la API."
                elif "base de datos" in mensaje_error:
                    error_chat = "El SQL se generó, pero MySQL no pudo ejecutarlo. Revisa las tablas y columnas disponibles."
                else:
                    error_chat = "No se pudo completar la consulta. Revisa el registro del servidor para ver en qué etapa falló."

    historial_html = ""
    for entrada in historial:
        pregunta_html = html.escape(str(entrada.get("pregunta", "")))
        respuesta_html = html.escape(str(entrada.get("respuesta", "")))
        sql_html = html.escape(str(entrada.get("sql", "")))
        historial_html += f"""
        <article class="py-4 border-bottom">
            <div class="d-flex justify-content-end mb-3">
                <div class="bg-primary text-white rounded-3 px-3 py-2" style="max-width: 85%; white-space: pre-wrap">{pregunta_html}</div>
            </div>
            <div class="d-flex align-items-start gap-2">
                <span class="text-primary fs-5"><i class="bi bi-stars"></i></span>
                <div class="flex-grow-1">
                    <p class="mb-2" style="white-space: pre-wrap">{respuesta_html}</p>
                    <details>
                        <summary class="small text-muted">Consulta SQL</summary>
                        <pre class="bg-light border rounded p-3 mt-2 mb-0 small text-break"><code>{sql_html}</code></pre>
                    </details>
                </div>
            </div>
        </article>
        """

    error_html = (
        f'<div class="alert alert-warning" role="alert">{html.escape(error_chat)}</div>'
        if error_chat else ""
    )
    vacio_html = """<div class="text-center text-muted py-5">
        <i class="bi bi-chat-square-text fs-1 d-block mb-3"></i>
        <p class="mb-1 fw-semibold">¿Qué necesitas consultar?</p>
        <p class="small mb-0">Pregunta sobre productos, stock, ventas o clientes.</p>
    </div>""" if not historial_html else ""

    contenido = f"""
    <div class="row justify-content-center">
        <div class="col-xl-9 col-lg-10">
            <header class="mb-4">
                <h1 class="h3 fw-bold mb-1"><i class="bi bi-chat-dots-fill text-primary me-2"></i>FerreterIA</h1>
                <p class="text-muted mb-0">Consultas de gestión en lenguaje natural con su SQL correspondiente.</p>
            </header>
            <section class="card border-0 shadow-sm">
                <div class="card-body px-3 px-md-4">
                    {error_html}
                    {vacio_html}
                    {historial_html}
                    <form method="post" class="pt-4">
                        <label class="form-label fw-semibold" for="preguntaFerreteria">Tu pregunta</label>
                        <div class="input-group">
                            <textarea id="preguntaFerreteria" name="pregunta" class="form-control" rows="2" maxlength="500" placeholder="Ej.: ¿Qué productos están por debajo del stock mínimo?" required></textarea>
                            <button type="submit" class="btn btn-primary px-3" title="Enviar consulta">
                                <i class="bi bi-send-fill"></i><span class="visually-hidden">Enviar</span>
                            </button>
                        </div>
                    </form>
                </div>
            </section>
        </div>
    </div>
    """
    return render_layout("FerreterIA", contenido, seccion_activa="ferreteria_ia")


# =====================================
# MENÚ PRINCIPAL / DASHBOARD
# =====================================

def _totales_ventas_recientes(cursor):
    cursor.execute("""
        SELECT COALESCE(SUM(CASE
                   WHEN fecha >= NOW() - INTERVAL 7 DAY THEN total ELSE 0
               END), 0) AS total_7_dias,
               COALESCE(SUM(CASE
                   WHEN fecha >= NOW() - INTERVAL 30 DAY THEN total ELSE 0
               END), 0) AS total_30_dias
        FROM venta
        WHERE estado = 'COMPLETADA'
    """)
    return cursor.fetchone()


@app.route("/")
def inicio():
    conteo_productos = 0
    conteo_clientes = 0
    conteo_alertas = 0
    conteo_proveedores = 0
    conteo_cheques_alerta = 0
    clientes_credito_alerta = []
    total_ventas_7_dias = Decimal("0.00")
    total_ventas_30_dias = Decimal("0.00")

    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        total_ventas_7_dias, total_ventas_30_dias = _totales_ventas_recientes(cursor)
        
        cursor.execute("SELECT COUNT(*) FROM producto")
        conteo_productos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM cliente")
        conteo_clientes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM v_stock_a_reponer")
        conteo_alertas = cursor.fetchone()[0]

        try:
            cursor.execute("SELECT COUNT(*) FROM proveedor WHERE activo = 1")
            conteo_proveedores = cursor.fetchone()[0]
        except Exception:
            conteo_proveedores = 0

        cursor.execute("""
            SELECT COUNT(*)
            FROM cheque
            WHERE estado IN ('EN_CARTERA', 'DEPOSITADO')
              AND fecha_cobro <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        """)
        conteo_cheques_alerta = cursor.fetchone()[0]

        cursor.execute("""
            SELECT cuenta.id_cliente,
                   cuenta.nombre,
                   cuenta.limite_credito,
                   GREATEST(cuenta.total_a_cuenta_corriente - cuenta.total_cobrado, 0) AS saldo_pendiente,
                   ROUND(
                       100 * GREATEST(cuenta.total_a_cuenta_corriente - cuenta.total_cobrado, 0)
                       / NULLIF(cuenta.limite_credito, 0),
                       1
                   ) AS porcentaje_limite
            FROM v_cuenta_corriente_clientes AS cuenta
            INNER JOIN cliente AS c ON c.id_cliente = cuenta.id_cliente
            WHERE c.activo = 1
              AND cuenta.limite_credito > 0
              AND GREATEST(cuenta.total_a_cuenta_corriente - cuenta.total_cobrado, 0)
                  > cuenta.limite_credito * 0.70
            ORDER BY porcentaje_limite DESC
        """)
        clientes_credito_alerta = cursor.fetchall()

    except Exception as e:
        print(f"Error consultando métricas dashboard: {e}")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    creditos_lista_html = "".join(
        f'<li><a href="/clientes" class="alert-link">{html.escape(str(cliente[1]))}</a>: '
        f'{float(cliente[4]):.1f}% del límite '
        f'(${float(cliente[3]):,.2f} / ${float(cliente[2]):,.2f})</li>'
        for cliente in clientes_credito_alerta
    )
    if not creditos_lista_html:
        creditos_lista_html = '<li class="text-muted">Ningún cliente supera el 70% de su límite.</li>'

    alerta_reposicion_clase = "danger" if conteo_alertas else "success"
    alerta_cheques_clase = "warning" if conteo_cheques_alerta else "success"
    alerta_credito_clase = "danger" if clientes_credito_alerta else "success"

    contenido = f"""
    <!-- ENCABEZADO PANEL -->
    <div class="row align-items-center mb-4">
        <div class="col-md-8">
            <h1 class="h3 fw-bold mb-1 text-dark">Panel de Control General</h1>
            <p class="text-muted mb-0">Bienvenido al sistema de administración de stock y ventas de Ferretería CANJER.</p>
        </div>
        {'' if rol_actual() == "ADMINISTRACION" else '''<div class="col-md-4 text-md-end mt-3 mt-md-0">
            <a href="/productos/nuevo" class="btn btn-primary shadow-sm">
                <i class="bi bi-plus-circle"></i> Nuevo Producto
            </a>
        </div>'''}
    </div>

    <section aria-labelledby="titulo-alertas" class="mb-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <div>
                <h2 id="titulo-alertas" class="h5 fw-bold mb-1"><i class="bi bi-bell-fill text-warning me-2"></i>Alertas</h2>
                <p class="small text-muted mb-0">Reposición, vencimientos de cheques y uso del crédito de clientes.</p>
            </div>
            <a href="/alertas" class="btn btn-sm btn-outline-secondary">Ver todas</a>
        </div>
        <div class="row g-3">
            <div class="col-md-4">
                <article class="card h-100 border-start border-4 border-{alerta_reposicion_clase} shadow-sm">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start gap-2">
                            <div>
                                <h3 class="h6 fw-bold mb-1">Reposición</h3>
                                <p class="small text-muted mb-2">Productos en stock mínimo o por debajo.</p>
                            </div>
                            <span class="badge text-bg-{alerta_reposicion_clase}">{conteo_alertas}</span>
                        </div>
                        <a href="/alertas" class="small fw-semibold text-decoration-none">Revisar productos <i class="bi bi-arrow-right"></i></a>
                    </div>
                </article>
            </div>
            <div class="col-md-4">
                <article class="card h-100 border-start border-4 border-{alerta_cheques_clase} shadow-sm">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start gap-2">
                            <div>
                                <h3 class="h6 fw-bold mb-1">Cheques</h3>
                                <p class="small text-muted mb-2">Pendientes vencidos o que vencen en 7 días.</p>
                            </div>
                            <span class="badge text-bg-{alerta_cheques_clase}">{conteo_cheques_alerta}</span>
                        </div>
                        <a href="/alertas#alertas-cheques" class="small fw-semibold text-decoration-none">Revisar cheques <i class="bi bi-arrow-right"></i></a>
                    </div>
                </article>
            </div>
            <div class="col-md-4">
                <article class="card h-100 border-start border-4 border-{alerta_credito_clase} shadow-sm">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start gap-2">
                            <div>
                                <h3 class="h6 fw-bold mb-1">Cuenta corriente</h3>
                                <p class="small text-muted mb-2">Clientes con saldo superior al 70% del límite.</p>
                            </div>
                            <span class="badge text-bg-{alerta_credito_clase}">{len(clientes_credito_alerta)}</span>
                        </div>
                        <ul class="small ps-3 mb-2">{creditos_lista_html}</ul>
                        <a href="/clientes" class="small fw-semibold text-decoration-none">Ver clientes <i class="bi bi-arrow-right"></i></a>
                    </div>
                </article>
            </div>
        </div>
    </section>

    <section aria-labelledby="titulo-ventas-recientes" class="mb-4">
        <h2 id="titulo-ventas-recientes" class="h5 fw-bold mb-3">Ventas acumuladas</h2>
        <div class="row g-3">
            <div class="col-md-6">
                <article class="card border-start border-4 border-success shadow-sm h-100">
                    <div class="card-body">
                        <span class="text-uppercase text-secondary fw-semibold small">Últimos 7 días</span>
                        <div class="h3 fw-bold text-dark mt-2 mb-0">${float(total_ventas_7_dias):,.2f}</div>
                    </div>
                </article>
            </div>
            <div class="col-md-6">
                <article class="card border-start border-4 border-primary shadow-sm h-100">
                    <div class="card-body">
                        <span class="text-uppercase text-secondary fw-semibold small">Últimos 30 días</span>
                        <div class="h3 fw-bold text-dark mt-2 mb-0">${float(total_ventas_30_dias):,.2f}</div>
                    </div>
                </article>
            </div>
        </div>
    </section>

    <!-- TARJETAS DE MÉTRICAS -->
    <div class="row g-3 mb-4">
        <div class="col-sm-6 col-xl-3">
            <div class="card metric-card shadow-sm p-3 h-100" style="border-left-color: #3b82f6;">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="text-uppercase text-secondary fw-semibold small">Total Productos</span>
                        <h2 class="h3 fw-bold text-dark mt-1 mb-0">{conteo_productos}</h2>
                    </div>
                    <div class="bg-primary bg-opacity-10 text-primary p-3 rounded-circle">
                        <i class="bi bi-box-seam fs-3"></i>
                    </div>
                </div>
                <div class="mt-3">
                    <a href="/productos" class="small text-decoration-none fw-semibold text-primary">
                        Ir al catálogo <i class="bi bi-arrow-right"></i>
                    </a>
                </div>
            </div>
        </div>

        <div class="col-sm-6 col-xl-3">
            <div class="card metric-card shadow-sm p-3 h-100" style="border-left-color: #10b981;">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="text-uppercase text-secondary fw-semibold small">Clientes Activos</span>
                        <h2 class="h3 fw-bold text-dark mt-1 mb-0">{conteo_clientes}</h2>
                    </div>
                    <div class="bg-success bg-opacity-10 text-success p-3 rounded-circle">
                        <i class="bi bi-people fs-3"></i>
                    </div>
                </div>
                <div class="mt-3">
                    <a href="/clientes" class="small text-decoration-none fw-semibold text-success">
                        Ver cartera de clientes <i class="bi bi-arrow-right"></i>
                    </a>
                </div>
            </div>
        </div>

        <div class="col-sm-6 col-xl-3">
            <div class="card metric-card shadow-sm p-3 h-100" style="border-left-color: #06b6d4;">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="text-uppercase text-secondary fw-semibold small">Proveedores</span>
                        <h2 class="h3 fw-bold text-dark mt-1 mb-0">{conteo_proveedores}</h2>
                    </div>
                    <div class="bg-info bg-opacity-10 text-info p-3 rounded-circle">
                        <i class="bi bi-truck fs-3"></i>
                    </div>
                </div>
                <div class="mt-3">
                    <a href="/proveedores" class="small text-decoration-none fw-semibold text-info">
                        Ver proveedores <i class="bi bi-arrow-right"></i>
                    </a>
                </div>
            </div>
        </div>

        <div class="col-sm-6 col-xl-3">
            <div class="card metric-card shadow-sm p-3 h-100" style="border-left-color: #ef4444;">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="text-uppercase text-secondary fw-semibold small">Productos por reponer</span>
                        <h2 class="h3 fw-bold text-dark mt-1 mb-0">{conteo_alertas}</h2>
                    </div>
                    <div class="bg-danger bg-opacity-10 text-danger p-3 rounded-circle">
                        <i class="bi bi-bell-fill fs-3"></i>
                    </div>
                </div>
                <div class="mt-3">
                    <a href="/alertas" class="small text-decoration-none fw-semibold text-danger">
                        Ver reposiciones <i class="bi bi-arrow-right"></i>
                    </a>
                </div>
            </div>
        </div>
    </div>

    <!-- ACCESOS RÁPIDOS DESTACADOS -->
    <div class="card shadow-sm border-0 mb-4">
        <div class="card-header bg-white py-3 border-bottom d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2">
            <h5 class="card-title fw-bold text-dark mb-0 d-flex align-items-center gap-2">
                <i class="bi bi-lightning-charge-fill text-warning"></i> Accesos Rápidos
            </h5>
        </div>
        <div class="card-body p-4">
            <div class="row g-3">
                <div class="col-md-6 col-lg-3">
                    <a href="/productos" class="card h-100 text-decoration-none p-3 border border-light-subtle bg-body-tertiary hover-shadow">
                        <div class="d-flex align-items-center gap-3">
                            <span class="fs-1 text-primary">📦</span>
                            <div>
                                <h6 class="fw-bold text-dark mb-1">Catálogo de Productos</h6>
                                <p class="small text-muted mb-0">Precios, stock actual y gestión de inventario.</p>
                            </div>
                        </div>
                    </a>
                </div>
                <div class="col-md-6 col-lg-3">
                    <a href="/ventas/" class="card h-100 text-decoration-none p-3 border border-light-subtle bg-body-tertiary hover-shadow">
                        <div class="d-flex align-items-center gap-3">
                            <span class="fs-1 text-success"><i class="bi bi-cart-check-fill"></i></span>
                            <div>
                                <h6 class="fw-bold text-dark mb-1">Módulo de Ventas</h6>
                                <p class="small text-muted mb-0">Registrar operaciones, consultar comprobantes y anulaciones.</p>
                            </div>
                        </div>
                    </a>
                </div>
                <div class="col-md-6 col-lg-3">
                    <a href="/clientes" class="card h-100 text-decoration-none p-3 border border-light-subtle bg-body-tertiary hover-shadow">
                        <div class="d-flex align-items-center gap-3">
                            <span class="fs-1 text-success">👥</span>
                            <div>
                                <h6 class="fw-bold text-dark mb-1">Gestión de Clientes</h6>
                                <p class="small text-muted mb-0">Cuentas, tipos y límites de crédito.</p>
                            </div>
                        </div>
                    </a>
                </div>
                <div class="col-md-6 col-lg-3">
                    <a href="/proveedores" class="card h-100 text-decoration-none p-3 border border-light-subtle bg-body-tertiary hover-shadow">
                        <div class="d-flex align-items-center gap-3">
                            <span class="fs-1 text-info">🚚</span>
                            <div>
                                <h6 class="fw-bold text-dark mb-1">Directorio Proveedores</h6>
                                <p class="small text-muted mb-0">Contactos comerciales y compras.</p>
                            </div>
                        </div>
                    </a>
                </div>
                <div class="col-md-6 col-lg-3">
                    <a href="/alertas" class="card h-100 text-decoration-none p-3 border border-light-subtle bg-body-tertiary hover-shadow">
                        <div class="d-flex align-items-center gap-3">
                            <span class="fs-1 text-danger">⚠️</span>
                            <div>
                                <h6 class="fw-bold text-dark mb-1">Centro de Alertas</h6>
                                <p class="small text-muted mb-0">Reposición, cheques y límites de cuenta corriente.</p>
                            </div>
                        </div>
                    </a>
                </div>
                <div class="col-md-6 col-lg-3">
                    <a href="/analisis/" class="card h-100 text-decoration-none p-3 border border-light-subtle bg-body-tertiary hover-shadow">
                        <div class="d-flex align-items-center gap-3">
                            <span class="fs-1 text-primary"><i class="bi bi-graph-up-arrow"></i></span>
                            <div>
                                <h6 class="fw-bold text-dark mb-1">Análisis de datos</h6>
                                <p class="small text-muted mb-0">Exporta ventas, cuentas, cheques y stock a CSV.</p>
                            </div>
                        </div>
                    </a>
                </div>
            </div>
        </div>
    </div>
    <p class="text-center text-muted small mt-4 mb-0">
        APP realizada por Eva Sacco · <a href="mailto:evasacco@gmail.com" class="link-secondary">evasacco@gmail.com</a>
    </p>
    """
    return render_layout("Panel Principal", contenido, seccion_activa="inicio")


# =====================================
# CRUD PRODUCTOS: LISTADO
# =====================================

@app.route("/productos")
def productos():
    es_deposito = rol_actual() == "DEPOSITO"
    es_propietario = rol_actual() in {"ADMIN", "ADMINISTRACION"}
    conexion = None
    cursor = None
    filas = []

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT p.codigo,
                   p.nombre,
                   p.precio_venta,
                   p.stock_actual,
                   p.stock_minimo,
                   c.nombre
            FROM producto AS p
            LEFT JOIN categoria AS c
                ON c.id_categoria = p.id_categoria
            ORDER BY p.nombre
        """)
        filas = cursor.fetchall()
    except Exception as e:
        flash(f"Error al cargar productos: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    filas_html = ""
    for fila in filas:
        codigo = html.escape(str(fila[0]), quote=True)
        nombre = html.escape(str(fila[1]))
        precio = float(fila[2])
        stock = int(fila[3])
        stock_minimo = int(fila[4])
        categoria = html.escape(str(fila[5] or "Sin categoría"))

        # Badge según estado de stock
        if stock <= stock_minimo:
            badge_stock = f'<span class="badge bg-danger-subtle text-danger border border-danger-subtle"><i class="bi bi-exclamation-triangle-fill me-1"></i>{stock} (Bajo)</span>'
        elif stock <= stock_minimo * 1.5:
            badge_stock = f'<span class="badge bg-warning-subtle text-warning-emphasis border border-warning-subtle"><i class="bi bi-info-circle me-1"></i>{stock}</span>'
        else:
            badge_stock = f'<span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-check-circle me-1"></i>{stock}</span>'

        precio_html = "" if es_deposito else f'<td class="fw-bold text-dark font-monospace">${precio:,.2f}</td>'
        if es_propietario:
            acciones_html = f"""
            <td class="text-end">
                <div class="btn-group btn-group-sm" role="group">
                    <a href="/productos/editar/{codigo}" class="btn btn-outline-primary" title="Editar">
                        <i class="bi bi-pencil-square"></i> Editar
                    </a>
                    <form action="/productos/eliminar/{codigo}" method="POST" class="d-inline" onsubmit="return confirm('¿Seguro que deseas eliminar permanentemente el producto {codigo}?');">
                        <button type="submit" class="btn btn-outline-danger" title="Eliminar"><i class="bi bi-trash"></i></button>
                    </form>
                </div>
            </td>
            """
        else:
            acciones_html = '<td class="text-end text-muted">Solo consulta</td>'

        filas_html += f"""
        <tr>
            <td class="fw-bold text-primary font-monospace">{codigo}</td>
            <td class="fw-semibold text-dark">{nombre}</td>
            {precio_html}
            <td>{badge_stock}</td>
            <td class="text-muted font-monospace">{stock_minimo}</td>
            <td><span class="badge bg-secondary-subtle text-secondary-emphasis">{categoria}</span></td>
            {acciones_html}
        </tr>
        """

    if not filas:
        filas_html = f"""
        <tr>
            <td colspan="{7 if not es_deposito else 6}" class="text-center text-muted py-5">
                <i class="bi bi-box-seam fs-1 d-block mb-2 text-secondary"></i>
                No se encontraron productos registrados en el sistema.
            </td>
        </tr>
        """

    contenido = f"""
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <h1 class="h3 fw-bold mb-1">Catálogo de Productos</h1>
            <p class="text-muted mb-0">Gestión de inventario, precios y existencias.</p>
        </div>
        <div class="d-flex gap-2">
            <a href="/" class="btn btn-outline-secondary">
                <i class="bi bi-arrow-left"></i> Volver al Panel
            </a>
            {('<a href="/productos/nuevo" class="btn btn-success shadow-sm"><i class="bi bi-plus-lg"></i> Registrar Producto</a>' if rol_actual() in {"ADMIN", "DEPOSITO"} else '')}
        </div>
    </div>

    <div class="card table-card shadow-sm border-0">
        <div class="card-header bg-white py-3 border-bottom d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2">
            <div class="d-flex align-items-center gap-2">
                <h5 class="fw-bold text-dark mb-0">Inventario Registrado</h5>
                <span class="badge bg-primary text-white rounded-pill">{len(filas)}</span>
            </div>
            <div class="col-md-4">
                <div class="input-group input-group-sm">
                    <span class="input-group-text bg-light border-end-0"><i class="bi bi-search text-muted"></i></span>
                    <input type="text" id="buscadorProductos" class="form-control border-start-0 bg-light" placeholder="Buscar por código, nombre o categoría...">
                </div>
            </div>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0" id="tablaProductos">
                <thead>
                    <tr>
                        <th>Código</th>
                        <th>Producto</th>
                        {'' if es_deposito else '<th>Precio Venta</th>'}
                        <th>Stock Actual</th>
                        <th>Stock Mín.</th>
                        <th>Categoría</th>
                        <th class="text-end">Acciones</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_html}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            inicializarBuscador('buscadorProductos', 'tablaProductos');
        }});
    </script>
    """
    return render_layout("Productos", contenido, seccion_activa="productos")


# =====================================
# CRUD PRODUCTOS: CREAR
# =====================================

def validar_datos_producto(codigo, nombre, precio_venta, stock_actual, stock_minimo, id_categoria, requiere_codigo=True):
    if requiere_codigo and not codigo:
        raise ValueError("El código es obligatorio.")
    if not nombre:
        raise ValueError("El nombre del producto es obligatorio.")

    try:
        precio = Decimal(precio_venta)
        stock = int(stock_actual)
        minimo = int(stock_minimo)
        categoria = int(id_categoria)
    except (InvalidOperation, ValueError):
        raise ValueError("Precio y stocks deben ser números válidos.")

    if not precio.is_finite() or precio < 0:
        raise ValueError("El precio debe ser mayor o igual a cero.")
    if stock < 0 or minimo < 0:
        raise ValueError("Los stocks no pueden ser negativos.")
    if categoria <= 0:
        raise ValueError("Selecciona una categoría válida.")

    return codigo, nombre, precio, stock, minimo, categoria


@app.route("/productos/nuevo", methods=["GET", "POST"])
def productos_nuevo():
    es_deposito = rol_actual() == "DEPOSITO"
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        nombre = request.form.get("nombre", "").strip()
        precio_venta = "0" if es_deposito else request.form.get("precio_venta", "").strip()
        stock_actual = request.form.get("stock_actual", "").strip()
        stock_minimo = request.form.get("stock_minimo", "").strip()
        id_categoria = request.form.get("id_categoria", "").strip()

        try:
            codigo, nombre, precio_venta, stock_actual, stock_minimo, id_categoria = validar_datos_producto(
                codigo,
                nombre,
                precio_venta,
                stock_actual,
                stock_minimo,
                id_categoria
            )
        except ValueError as error:
            flash(str(error), "warning")
            return redirect(url_for("productos_nuevo"))

        conexion = None
        cursor = None
        try:
            conexion = obtener_conexion()
            cursor = conexion.cursor()
            cursor.execute("""
                INSERT INTO producto
                    (codigo, nombre, precio_venta, stock_actual, stock_minimo, id_categoria)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (codigo, nombre, precio_venta, stock_actual, stock_minimo, id_categoria))
            conexion.commit()
            flash(f"Producto '{nombre}' agregado exitosamente.", "success")
            return redirect(url_for("productos"))
        except Exception as e:
            if conexion:
                conexion.rollback()
            flash(f"Error al registrar producto: {e}", "danger")
        finally:
            if cursor:
                cursor.close()
            if conexion:
                conexion.close()

    categorias = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT id_categoria, nombre FROM categoria ORDER BY nombre")
        categorias = cursor.fetchall()
    except Exception as error:
        flash(f"No se pudieron cargar las categorías: {error}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    categorias_html = "".join(
        f'<option value="{int(id_categoria)}">{html.escape(str(nombre))}</option>'
        for id_categoria, nombre in categorias
    )
    if es_deposito:
        campo_precio_html = '<div class="col-12"><div class="alert alert-info mb-0">El precio de venta quedará pendiente para que lo complete el propietario.</div></div>'
    else:
        campo_precio_html = """<div class="col-md-4">
            <label class="form-label fw-semibold text-secondary">Precio de Venta ($):</label>
            <div class="input-group">
                <span class="input-group-text bg-light">$</span>
                <input type="number" step="0.01" min="0" name="precio_venta" class="form-control" placeholder="0.00" required>
            </div>
        </div>"""

    contenido = f"""
    <div class="row justify-content-center">
        <div class="col-lg-7 col-md-9">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <a href="/productos" class="btn btn-outline-secondary">
                    <i class="bi bi-arrow-left"></i> Cancelar y Volver
                </a>
            </div>

            <div class="card shadow-sm border-0">
                <div class="card-header bg-success text-white py-3">
                    <h5 class="fw-bold mb-0 d-flex align-items-center gap-2">
                        <i class="bi bi-plus-square"></i> Registrar Nuevo Producto
                    </h5>
                </div>
                <div class="card-body p-4">
                    <form method="POST" action="/productos/nuevo">
                        <div class="row g-3">
                            <div class="col-md-4">
                                <label class="form-label fw-semibold text-secondary">Código (*):</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light"><i class="bi bi-upc"></i></span>
                                    <input type="text" name="codigo" class="form-control" placeholder="Ej: P001" required autofocus>
                                </div>
                            </div>
                            <div class="col-md-8">
                                <label class="form-label fw-semibold text-secondary">Nombre del Producto (*):</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light"><i class="bi bi-tag"></i></span>
                                    <input type="text" name="nombre" class="form-control" placeholder="Ej: Martillo Galponero 16oz" required>
                                </div>
                            </div>

                            {campo_precio_html}
                            <div class="col-md-4">
                                <label class="form-label fw-semibold text-secondary">Stock Inicial:</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light"><i class="bi bi-boxes"></i></span>
                                    <input type="number" step="1" min="0" name="stock_actual" class="form-control" placeholder="0" required>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <label class="form-label fw-semibold text-secondary">Stock Mínimo:</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light"><i class="bi bi-shield-exclamation"></i></span>
                                    <input type="number" step="1" min="0" name="stock_minimo" class="form-control" value="5" required>
                                </div>
                            </div>

                            <div class="col-12">
                                <label class="form-label fw-semibold text-secondary">Categoría (*):</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-light"><i class="bi bi-diagram-3"></i></span>
                                    <select name="id_categoria" class="form-select" required>
                                        <option value="">Selecciona una categoría...</option>
                                        {categorias_html}
                                    </select>
                                </div>
                            </div>
                        </div>

                        <hr class="my-4">

                        <div class="d-flex justify-content-end gap-2">
                            <a href="/productos" class="btn btn-light px-4">Cancelar</a>
                            <button type="submit" class="btn btn-success px-4 shadow-sm">
                                <i class="bi bi-check-lg"></i> Guardar Producto
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """
    return render_layout("Nuevo Producto", contenido, seccion_activa="productos")


# =====================================
# CRUD PRODUCTOS: EDITAR
# =====================================

@app.route("/productos/editar/<codigo>", methods=["GET", "POST"])
def productos_editar(codigo):
    conexion = None
    cursor = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        precio_venta = request.form.get("precio_venta", "").strip()
        stock_actual = request.form.get("stock_actual", "").strip()
        stock_minimo = request.form.get("stock_minimo", "").strip()
        id_categoria = request.form.get("id_categoria", "").strip()

        try:
            _, nombre, precio_venta, stock_actual, stock_minimo, id_categoria = validar_datos_producto(
                codigo,
                nombre,
                precio_venta,
                stock_actual,
                stock_minimo,
                id_categoria,
                requiere_codigo=False
            )
        except ValueError as error:
            flash(str(error), "warning")
            return redirect(url_for("productos_editar", codigo=codigo))

        try:
            conexion = obtener_conexion()
            cursor = conexion.cursor()
            cursor.execute("""
                UPDATE producto
                SET nombre = %s,
                    precio_venta = %s,
                    stock_actual = %s,
                    stock_minimo = %s,
                    id_categoria = %s
                WHERE codigo = %s
            """, (nombre, precio_venta, stock_actual, stock_minimo, id_categoria, codigo))
            conexion.commit()
            flash(f"Producto '{codigo}' actualizado correctamente.", "success")
            return redirect(url_for("productos"))
        except Exception as e:
            if conexion:
                conexion.rollback()
            flash(f"Error al actualizar producto: {e}", "danger")
        finally:
            if cursor:
                cursor.close()
            if conexion:
                conexion.close()

    producto = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT codigo, nombre, precio_venta, stock_actual, stock_minimo, id_categoria
            FROM producto
            WHERE codigo = %s
        """, (codigo,))
        producto = cursor.fetchone()
    except Exception as e:
        flash(f"Error al obtener el producto: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    categorias = []
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT id_categoria, nombre FROM categoria ORDER BY nombre")
        categorias = cursor.fetchall()
    except Exception as error:
        flash(f"No se pudieron cargar las categorías: {error}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    if not producto:
        flash("El producto solicitado no existe.", "warning")
        return redirect(url_for("productos"))

    prod_codigo = html.escape(str(producto[0]))
    prod_nombre = html.escape(str(producto[1]))
    prod_precio = html.escape(str(producto[2]))
    prod_stock = html.escape(str(producto[3]))
    prod_stock_minimo = html.escape(str(producto[4]))
    id_categoria_actual = int(producto[5])

    categorias_html = "".join(
        f'<option value="{int(id_c)}"'
        f'{" selected" if int(id_c) == id_categoria_actual else ""}>'
        f'{html.escape(str(nom))}</option>'
        for id_c, nom in categorias
    )

    contenido = f"""
    <div class="row justify-content-center">
        <div class="col-lg-7 col-md-9">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <a href="/productos" class="btn btn-outline-secondary">
                    <i class="bi bi-arrow-left"></i> Cancelar y Volver
                </a>
            </div>

            <div class="card shadow-sm border-0">
                <div class="card-header bg-primary text-white py-3">
                    <h5 class="fw-bold mb-0 d-flex align-items-center gap-2">
                        <i class="bi bi-pencil-square"></i> Modificar Producto: {prod_codigo}
                    </h5>
                </div>
                <div class="card-body p-4">
                    <form method="POST" action="/productos/editar/{prod_codigo}">
                        <div class="row g-3">
                            <div class="col-md-4">
                                <label class="form-label fw-semibold text-secondary">Código:</label>
                                <input type="text" class="form-control bg-light font-monospace fw-bold" value="{prod_codigo}" disabled readonly>
                            </div>
                            <div class="col-md-8">
                                <label class="form-label fw-semibold text-secondary">Nombre del Producto (*):</label>
                                <input type="text" name="nombre" class="form-control" value="{prod_nombre}" required>
                            </div>

                            <div class="col-md-4">
                                <label class="form-label fw-semibold text-secondary">Precio de Venta ($):</label>
                                <div class="input-group">
                                    <span class="input-group-text">$</span>
                                    <input type="number" step="0.01" min="0" name="precio_venta" class="form-control" value="{prod_precio}" required>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <label class="form-label fw-semibold text-secondary">Stock Actual:</label>
                                <input type="number" step="1" min="0" name="stock_actual" class="form-control" value="{prod_stock}" required>
                            </div>
                            <div class="col-md-4">
                                <label class="form-label fw-semibold text-secondary">Stock Mínimo:</label>
                                <input type="number" step="1" min="0" name="stock_minimo" class="form-control" value="{prod_stock_minimo}" required>
                            </div>

                            <div class="col-12">
                                <label class="form-label fw-semibold text-secondary">Categoría (*):</label>
                                <select name="id_categoria" class="form-select" required>
                                    {categorias_html}
                                </select>
                            </div>
                        </div>

                        <hr class="my-4">

                        <div class="d-flex justify-content-end gap-2">
                            <a href="/productos" class="btn btn-light px-4">Cancelar</a>
                            <button type="submit" class="btn btn-primary px-4 shadow-sm">
                                <i class="bi bi-save"></i> Guardar Cambios
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """
    return render_layout("Editar Producto", contenido, seccion_activa="productos")


# =====================================
# CRUD PRODUCTOS: ELIMINAR
# =====================================

@app.route("/productos/eliminar/<codigo>", methods=["POST"])
def productos_eliminar(codigo):
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("DELETE FROM producto WHERE codigo = %s", (codigo,))
        conexion.commit()
        flash(f"Producto '{codigo}' eliminado satisfactoriamente.", "success")
    except Exception as e:
        if conexion:
            conexion.rollback()
        flash(f"Error al eliminar producto: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    return redirect(url_for("productos"))


# =====================================
# CLIENTES
# =====================================

@app.route("/clientes")
def clientes():
    estado = request.args.get("estado", "activos")
    if estado not in {"activos", "inactivos", "todos"}:
        estado = "activos"
    puede_gestionar = rol_actual() in {"ADMIN", "ADMINISTRACION"}
    conexion = None
    cursor = None
    filas = []

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        condicion = "WHERE activo = 1" if estado == "activos" else "WHERE activo = 0" if estado == "inactivos" else ""
        cursor.execute(f"""
            SELECT id_cliente, nombre, tipo, telefono, limite_credito, activo
            FROM cliente
            {condicion}
            ORDER BY nombre
        """)
        filas = cursor.fetchall()
    except Exception as e:
        flash(f"Error al cargar clientes: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    filas_html = ""
    for fila in filas:
        id_cliente = int(fila[0])
        nombre = html.escape(str(fila[1]))
        tipo = html.escape(str(fila[2]))
        telefono = html.escape(str(fila[3] or "—"))
        limite = float(fila[4])
        activo = bool(fila[5])

        etiqueta_tipo = {
            "CONSUMIDOR_FINAL": "Consumidor final",
            "EMPRESA": "Empresa",
            "INSTITUCIONAL": "Institucional",
        }.get(str(fila[2]), str(fila[2]))
        badge_tipo = f'<span class="badge bg-info-subtle text-info-emphasis border border-info-subtle">{html.escape(etiqueta_tipo)}</span>'

        if puede_gestionar:
            etiqueta_estado = "Desactivar" if activo else "Reactivar"
            clase_estado = "outline-danger" if activo else "outline-success"
            icono_estado = "bi-person-dash" if activo else "bi-person-check"
            acciones_html = f"""
            <td class="text-end text-nowrap">
                <a class="btn btn-sm btn-outline-primary" href="{url_for('clientes_editar', id_cliente=id_cliente)}" title="Editar cliente">
                    <i class="bi bi-pencil"></i><span class="visually-hidden">Editar</span>
                </a>
                <form class="d-inline" method="post" action="{url_for('clientes_cambiar_estado', id_cliente=id_cliente)}">
                    <button class="btn btn-sm btn-{clase_estado}" type="submit" title="{etiqueta_estado} cliente">
                        <i class="bi {icono_estado}"></i><span class="visually-hidden">{etiqueta_estado}</span>
                    </button>
                </form>
            </td>
            """
        else:
            acciones_html = ""

        filas_html += f"""
        <tr>
            <td class="fw-bold text-dark">{nombre}</td>
            <td>{badge_tipo}</td>
            <td>{telefono}</td>
            <td class="fw-semibold font-monospace">${limite:,.2f}</td>
            <td><span class="badge text-bg-{'success' if activo else 'secondary'}">{'Activo' if activo else 'Inactivo'}</span></td>
            {acciones_html}
        </tr>
        """

    if not filas:
        filas_html = f"""
        <tr>
            <td colspan="{6 if puede_gestionar else 5}" class="text-center text-muted py-5">
                <i class="bi bi-people fs-1 d-block mb-2 text-secondary"></i>
                No hay clientes registrados en la base de datos.
            </td>
        </tr>
        """

    contenido = f"""
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <h1 class="h3 fw-bold mb-1">Cartera de Clientes</h1>
            <p class="text-muted mb-0">Listado de cuentas corrientes y límites de crédito asignados.</p>
        </div>
        <div>
            {f'<a href="{url_for("clientes_nuevo")}" class="btn btn-primary me-2"><i class="bi bi-plus-lg"></i> Nuevo cliente</a>' if puede_gestionar else ''}
            <a href="/cuenta-corriente" class="btn btn-outline-primary me-2">
                <i class="bi bi-credit-card-2-front"></i> Cuenta corriente
            </a>
            <a href="/" class="btn btn-outline-secondary">
                <i class="bi bi-arrow-left"></i> Volver al Panel
            </a>
        </div>
    </div>

    <div class="card table-card shadow-sm border-0">
        <div class="card-header bg-white py-3 border-bottom d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2">
            <div class="d-flex align-items-center gap-2">
                <h5 class="fw-bold text-dark mb-0">Clientes</h5>
                <span class="badge bg-success text-white rounded-pill">{len(filas)}</span>
            </div>
            <div class="d-flex gap-2 align-items-end">
                <form method="get" class="d-flex gap-2 align-items-end">
                    <div><label class="form-label small mb-1" for="estadoCliente">Estado</label>
                        <select id="estadoCliente" name="estado" class="form-select form-select-sm">
                            <option value="activos" {'selected' if estado == 'activos' else ''}>Activos</option>
                            <option value="inactivos" {'selected' if estado == 'inactivos' else ''}>Inactivos</option>
                            <option value="todos" {'selected' if estado == 'todos' else ''}>Todos</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-sm btn-outline-primary" title="Filtrar"><i class="bi bi-funnel"></i></button>
                </form>
                <div class="input-group input-group-sm" style="max-width: 240px">
                    <span class="input-group-text bg-light border-end-0"><i class="bi bi-search text-muted"></i></span>
                    <input type="text" id="buscadorClientes" class="form-control border-start-0 bg-light" placeholder="Buscar cliente...">
                </div>
            </div>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0" id="tablaClientes">
                <thead>
                    <tr>
                        <th>Nombre y Apellido / Razón Social</th>
                        <th>Tipo de Cliente</th>
                        <th>Teléfono</th>
                        <th>Límite de Crédito</th>
                        <th>Estado</th>
                        {"<th>Acciones</th>" if puede_gestionar else ""}
                    </tr>
                </thead>
                <tbody>
                    {filas_html}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            inicializarBuscador('buscadorClientes', 'tablaClientes');
        }});
    </script>
    """
    return render_layout("Clientes", contenido, seccion_activa="clientes")


TIPOS_CLIENTE = {
    "CONSUMIDOR_FINAL": "Consumidor final",
    "EMPRESA": "Empresa",
    "INSTITUCIONAL": "Institucional",
}


def validar_datos_cliente(nombre, tipo, telefono):
    nombre = str(nombre or "").strip()
    tipo = str(tipo or "").strip()
    telefono = str(telefono or "").strip() or None
    if not nombre:
        raise ValueError("El nombre o razón social es obligatorio.")
    if tipo not in TIPOS_CLIENTE:
        raise ValueError("Selecciona un tipo de cliente válido.")
    return nombre, tipo, telefono


@app.route("/clientes/nuevo", methods=["GET", "POST"])
def clientes_nuevo():
    if request.method == "POST":
        try:
            nombre, tipo, telefono = validar_datos_cliente(
                request.form.get("nombre"),
                request.form.get("tipo"),
                request.form.get("telefono"),
            )
        except ValueError as error:
            flash(str(error), "warning")
            return redirect(url_for("clientes_nuevo"))

        conexion = None
        cursor = None
        try:
            conexion = obtener_conexion()
            cursor = conexion.cursor()
            cursor.execute("""
                INSERT INTO cliente (nombre, tipo, telefono, limite_credito, activo)
                VALUES (%s, %s, %s, 0.00, 1)
            """, (nombre, tipo, telefono))
            conexion.commit()
            flash(f"Cliente '{nombre}' registrado con límite de crédito en $0.00.", "success")
            return redirect(url_for("clientes"))
        except Exception as error:
            if conexion:
                conexion.rollback()
            flash(f"No se pudo registrar el cliente: {error}", "danger")
        finally:
            if cursor:
                cursor.close()
            if conexion:
                conexion.close()

    opciones_tipo = "".join(
        f'<option value="{clave}">{etiqueta}</option>'
        for clave, etiqueta in TIPOS_CLIENTE.items()
    )
    contenido = f"""
    <div class="row justify-content-center"><div class="col-lg-7">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h1 class="h3 fw-bold mb-0">Nuevo cliente</h1>
            <a href="{url_for('clientes')}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
        </div>
        <section class="card border-0 shadow-sm"><div class="card-body p-4">
            <form method="post">
                <div class="mb-3"><label class="form-label" for="nombreCliente">Nombre o razón social</label>
                    <input id="nombreCliente" class="form-control" name="nombre" required autofocus></div>
                <div class="row g-3">
                    <div class="col-md-6"><label class="form-label" for="tipoCliente">Tipo</label>
                        <select id="tipoCliente" class="form-select" name="tipo" required>{opciones_tipo}</select></div>
                    <div class="col-md-6"><label class="form-label" for="telefonoCliente">Teléfono</label>
                        <input id="telefonoCliente" class="form-control" name="telefono" type="tel"></div>
                </div>
                <p class="form-text mt-3">El cliente se registra con límite de crédito $0.00. El Propietario podrá modificarlo desde Cuenta corriente.</p>
                <div class="d-flex justify-content-end gap-2 mt-4">
                    <a href="{url_for('clientes')}" class="btn btn-light">Cancelar</a>
                    <button class="btn btn-primary" type="submit"><i class="bi bi-check-lg"></i> Registrar cliente</button>
                </div>
            </form>
        </div></section>
    </div></div>
    """
    return render_layout("Nuevo cliente", contenido, seccion_activa="clientes")


@app.route("/clientes/editar/<int:id_cliente>", methods=["GET", "POST"])
def clientes_editar(id_cliente):
    if request.method == "POST":
        try:
            nombre, tipo, telefono = validar_datos_cliente(
                request.form.get("nombre"),
                request.form.get("tipo"),
                request.form.get("telefono"),
            )
        except ValueError as error:
            flash(str(error), "warning")
            return redirect(url_for("clientes_editar", id_cliente=id_cliente))

        conexion = None
        cursor = None
        try:
            conexion = obtener_conexion()
            cursor = conexion.cursor()
            cursor.execute("""
                UPDATE cliente
                SET nombre = %s, tipo = %s, telefono = %s
                WHERE id_cliente = %s
            """, (nombre, tipo, telefono, id_cliente))
            if cursor.rowcount == 0:
                cursor.execute("SELECT id_cliente FROM cliente WHERE id_cliente = %s", (id_cliente,))
                if not cursor.fetchone():
                    flash("El cliente no existe.", "warning")
                    return redirect(url_for("clientes"))
            conexion.commit()
            flash("Datos del cliente actualizados.", "success")
            return redirect(url_for("clientes"))
        except Exception as error:
            if conexion:
                conexion.rollback()
            flash(f"No se pudo actualizar el cliente: {error}", "danger")
        finally:
            if cursor:
                cursor.close()
            if conexion:
                conexion.close()

    cliente = None
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT nombre, tipo, telefono
            FROM cliente
            WHERE id_cliente = %s
        """, (id_cliente,))
        cliente = cursor.fetchone()
    except Exception as error:
        flash(f"No se pudo cargar el cliente: {error}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    if not cliente:
        flash("El cliente solicitado no existe.", "warning")
        return redirect(url_for("clientes"))

    nombre_actual = html.escape(str(cliente[0]), quote=True)
    telefono_actual = html.escape(str(cliente[2] or ""), quote=True)
    opciones_tipo = "".join(
        f'<option value="{clave}"{" selected" if str(cliente[1]) == clave else ""}>{etiqueta}</option>'
        for clave, etiqueta in TIPOS_CLIENTE.items()
    )
    contenido = f"""
    <div class="row justify-content-center"><div class="col-lg-7">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h1 class="h3 fw-bold mb-0">Editar cliente</h1>
            <a href="{url_for('clientes')}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
        </div>
        <section class="card border-0 shadow-sm"><div class="card-body p-4">
            <form method="post">
                <div class="mb-3"><label class="form-label" for="nombreCliente">Nombre o razón social</label>
                    <input id="nombreCliente" class="form-control" name="nombre" value="{nombre_actual}" required autofocus></div>
                <div class="row g-3">
                    <div class="col-md-6"><label class="form-label" for="tipoCliente">Tipo</label>
                        <select id="tipoCliente" class="form-select" name="tipo" required>{opciones_tipo}</select></div>
                    <div class="col-md-6"><label class="form-label" for="telefonoCliente">Teléfono</label>
                        <input id="telefonoCliente" class="form-control" name="telefono" type="tel" value="{telefono_actual}"></div>
                </div>
                <p class="form-text mt-3">El límite de crédito se administra exclusivamente desde Cuenta corriente.</p>
                <div class="d-flex justify-content-end gap-2 mt-4">
                    <a href="{url_for('clientes')}" class="btn btn-light">Cancelar</a>
                    <button class="btn btn-primary" type="submit"><i class="bi bi-save"></i> Guardar cambios</button>
                </div>
            </form>
        </div></section>
    </div></div>
    """
    return render_layout("Editar cliente", contenido, seccion_activa="clientes")


@app.route("/clientes/estado/<int:id_cliente>", methods=["POST"])
def clientes_cambiar_estado(id_cliente):
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            UPDATE cliente
            SET activo = CASE WHEN activo = 1 THEN 0 ELSE 1 END
            WHERE id_cliente = %s
        """, (id_cliente,))
        if cursor.rowcount == 0:
            flash("El cliente no existe.", "warning")
        else:
            conexion.commit()
            flash("Estado del cliente actualizado.", "success")
    except Exception as error:
        if conexion:
            conexion.rollback()
        flash(f"No se pudo cambiar el estado del cliente: {error}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()
    return redirect(url_for("clientes"))


# =====================================
# CUENTA CORRIENTE
# =====================================

@app.route("/cuenta-corriente")
def cuenta_corriente():
    conexion = None
    cursor = None
    cuentas = []
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id_cliente,
                   nombre,
                   tipo,
                   limite_credito,
                   total_a_cuenta_corriente,
                   total_cobrado
            FROM v_cuenta_corriente_clientes
            ORDER BY nombre
        """)
        cuentas = cursor.fetchall()
    except Exception as error:
        flash(f"Error al consultar cuentas corrientes: {error}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    filas = ""
    es_admin = rol_actual() == "ADMIN"
    saldo_total = Decimal("0.00")
    for cuenta in cuentas:
        id_cliente, nombre, tipo, limite, cargos, cobros = cuenta
        limite = Decimal(str(limite))
        cargos = Decimal(str(cargos))
        cobros = Decimal(str(cobros))
        saldo = max(cargos - cobros, Decimal("0.00"))
        saldo_total += saldo
        porcentaje = (saldo / limite * 100) if limite > 0 else None
        porcentaje_html = f"{porcentaje:.1f}%" if porcentaje is not None else "Sin límite"
        clase_saldo = "text-danger fw-bold" if porcentaje is not None and porcentaje >= 70 else "fw-semibold"
        nombre_html = html.escape(str(nombre))
        tipo_html = html.escape(str(tipo))
        accion_limite = f"""
            <td class="text-end">
                <form method="post" action="{url_for('clientes_actualizar_limite', id_cliente=id_cliente)}" class="d-flex justify-content-end gap-1">
                    <label class="visually-hidden" for="limite-{id_cliente}">Nuevo límite de {nombre_html}</label>
                    <input id="limite-{id_cliente}" class="form-control form-control-sm text-end" style="width: 120px" type="number" name="limite_credito" min="0" step="0.01" value="{limite:.2f}" required>
                    <button class="btn btn-sm btn-outline-primary" type="submit" title="Guardar límite"><i class="bi bi-save"></i><span class="visually-hidden">Guardar</span></button>
                </form>
            </td>
        """ if es_admin else ""
        filas += f"""
        <tr>
            <td class="fw-semibold">{nombre_html}</td>
            <td>{tipo_html}</td>
            <td class="text-end">${limite:,.2f}</td>
            <td class="text-end">${cargos:,.2f}</td>
            <td class="text-end">${cobros:,.2f}</td>
            <td class="text-end {clase_saldo}">${saldo:,.2f}</td>
            <td class="text-end">{porcentaje_html}</td>
            {accion_limite}
        </tr>
        """

    if not filas:
        filas = f'<tr><td colspan="{8 if es_admin else 7}" class="py-4 text-center text-muted">No hay cuentas corrientes para mostrar.</td></tr>'

    contenido = f"""
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <h1 class="h3 fw-bold mb-1">Cuentas corrientes</h1>
            <p class="text-muted mb-0">Límites, cargos, cobros y saldo pendiente por cliente.</p>
        </div>
        <a href="/clientes" class="btn btn-outline-secondary"><i class="bi bi-people"></i> Clientes</a>
    </div>
    <section class="card border-0 shadow-sm">
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead><tr><th>Cliente</th><th>Tipo</th><th class="text-end">Límite</th><th class="text-end">Cargos CC</th><th class="text-end">Cobros</th><th class="text-end">Saldo pendiente</th><th class="text-end">Uso del límite</th>{'<th class="text-end">Editar límite</th>' if es_admin else ''}</tr></thead>
                <tbody>{filas}</tbody>
                <tfoot><tr class="table-light"><th colspan="5" class="text-end">Saldo total pendiente</th><th class="text-end">${saldo_total:,.2f}</th><th colspan="{2 if es_admin else 1}"></th></tr></tfoot>
            </table>
        </div>
        <div class="card-footer bg-white small text-muted">Los saldos en 70% o más se resaltan para facilitar el seguimiento.</div>
    </section>
    """
    return render_layout("Cuentas corrientes", contenido, seccion_activa="cuenta_corriente")


@app.route("/clientes/<int:id_cliente>/limite", methods=["POST"])
def clientes_actualizar_limite(id_cliente):
    if rol_actual() != "ADMIN":
        return redirect(url_for(inicio_actual()))

    try:
        limite = Decimal(request.form.get("limite_credito", ""))
        if not limite.is_finite() or limite < 0 or limite.as_tuple().exponent < -2:
            raise ValueError
    except (InvalidOperation, ValueError):
        flash("El límite debe ser un importe válido, no negativo y con hasta dos decimales.", "warning")
        return redirect(url_for("cuenta_corriente"))

    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            UPDATE cliente
            SET limite_credito = %s
            WHERE id_cliente = %s
        """, (limite, id_cliente))
        if cursor.rowcount == 0:
            flash("El cliente no existe o el límite no tuvo cambios.", "warning")
        else:
            conexion.commit()
            flash("Límite de crédito actualizado.", "success")
    except Exception as error:
        if conexion:
            conexion.rollback()
        flash(f"No se pudo actualizar el límite: {error}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()
    return redirect(url_for("cuenta_corriente"))


# =====================================
# ALERTAS DE STOCK
# =====================================

@app.route("/alertas")
def alertas():
    conexion = None
    cursor = None
    filas = []
    cheques_alerta = []

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT codigo,
                   producto,
                   stock_actual,
                   stock_minimo
            FROM v_stock_a_reponer
            ORDER BY stock_actual ASC
        """)
        filas = cursor.fetchall()
        cursor.execute("""
            SELECT c.id_cheque,
                   c.numero,
                   c.banco,
                   c.fecha_cobro,
                   c.estado,
                   p.tipo,
                   p.monto,
                   COALESCE(cl.nombre, pr.razon_social) AS contraparte,
                   DATEDIFF(c.fecha_cobro, CURDATE()) AS dias_restantes
            FROM cheque AS c
            INNER JOIN pago AS p ON p.id_pago = c.id_pago
            LEFT JOIN cliente AS cl ON cl.id_cliente = p.id_cliente
            LEFT JOIN proveedor AS pr ON pr.id_proveedor = p.id_proveedor
            WHERE c.estado IN ('EN_CARTERA', 'DEPOSITADO')
              AND c.fecha_cobro <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
            ORDER BY c.fecha_cobro, c.numero
        """)
        cheques_alerta = cursor.fetchall()
    except Exception as e:
        flash(f"Error consultando alertas: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    filas_html = ""
    for fila in filas:
        codigo = html.escape(str(fila[0]), quote=True)
        nombre = html.escape(str(fila[1]))
        stock = int(fila[2])
        minimo = int(fila[3])
        deficit = minimo - stock

        accion_stock = (
            f'<a href="/productos/editar/{codigo}" class="btn btn-sm btn-outline-primary">'
            '<i class="bi bi-arrow-up-circle"></i> Reponer</a>'
            if rol_actual() in {"ADMIN", "ADMINISTRACION"}
            else '<span class="text-muted small">Solo consulta</span>'
        )
        filas_html += f"""
        <tr>
            <td class="font-monospace fw-bold text-danger">{codigo}</td>
            <td class="fw-semibold text-dark">{nombre}</td>
            <td>
                <span class="badge bg-danger text-white fs-6">
                    <i class="bi bi-exclamation-octagon-fill me-1"></i> {stock}
                </span>
            </td>
            <td class="font-monospace text-muted">{minimo}</td>
            <td class="fw-bold text-danger">+{deficit} u.</td>
            <td class="text-end">{accion_stock}</td>
        </tr>
        """

    if not filas:
        filas_html = """
        <tr>
            <td colspan="6" class="text-center text-success py-5">
                <i class="bi bi-check-circle-fill fs-1 d-block mb-2 text-success"></i>
                <span class="fw-bold">¡Excelente! Todos los productos cuentan con stock suficiente.</span>
            </td>
        </tr>
        """

    filas_cheques = ""
    for cheque in cheques_alerta:
        id_cheque, numero, banco, fecha_cobro, estado, tipo, monto, contraparte, dias = cheque
        if dias < 0:
            vencimiento = f"Vencido hace {abs(dias)} día(s)"
            clase_vencimiento = "text-danger fw-bold"
        elif dias == 0:
            vencimiento = "Vence hoy"
            clase_vencimiento = "text-danger fw-bold"
        else:
            vencimiento = f"Vence en {dias} día(s)"
            clase_vencimiento = "text-warning-emphasis fw-semibold"
        numero_html = html.escape(str(numero))
        banco_html = html.escape(str(banco))
        contraparte_html = html.escape(str(contraparte or "Sin contraparte"))
        monto_html = html.escape(f"${float(monto):,.2f}")
        fecha_html = fecha_cobro.strftime("%d/%m/%Y") if hasattr(fecha_cobro, "strftime") else html.escape(str(fecha_cobro))
        tipo_html = "Recibido" if tipo == "COBRO" else "Emitido"
        filas_cheques += f"""
        <tr>
            <td class="font-monospace fw-semibold">{numero_html}</td>
            <td>{banco_html}</td>
            <td>{tipo_html}</td>
            <td>{contraparte_html}</td>
            <td class="text-end">{monto_html}</td>
            <td>{fecha_html}</td>
            <td class="{clase_vencimiento}">{vencimiento}</td>
            <td><span class="badge text-bg-warning">{estado.replace('_', ' ').title()}</span></td>
        </tr>
        """

    if not filas_cheques:
        filas_cheques = '<tr><td colspan="8" class="py-4 text-center text-success">No hay cheques pendientes vencidos o próximos a vencer.</td></tr>'

    contenido = f"""
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <h1 class="h3 fw-bold mb-1 text-danger d-flex align-items-center gap-2">
                <i class="bi bi-bell-fill"></i> Alertas de Stock a Reponer
            </h1>
            <p class="text-muted mb-0">Productos cuyas unidades actuales están por debajo o al límite del stock mínimo definido.</p>
        </div>
        <div>
            <a href="/" class="btn btn-outline-secondary">
                <i class="bi bi-arrow-left"></i> Volver al Panel
            </a>
        </div>
    </div>

    <div class="card table-card shadow-sm border-0 border-top border-4 border-danger">
        <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
            <h5 class="fw-bold text-danger mb-0 d-flex align-items-center gap-2">
                <i class="bi bi-shield-exclamation"></i> Artículos en Estado Crítico
            </h5>
            <span class="badge bg-danger text-white rounded-pill">{len(filas)} requeridos</span>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead>
                    <tr>
                        <th>Código</th>
                        <th>Producto</th>
                        <th>Stock Actual</th>
                        <th>Stock Mínimo</th>
                        <th>Déficit Estimado</th>
                        <th class="text-end">Acción</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_html}
                </tbody>
            </table>
        </div>
    </div>

    <section id="alertas-cheques" class="card table-card shadow-sm border-0 border-top border-4 border-warning mt-4">
        <div class="card-header bg-white py-3 border-bottom d-flex flex-column flex-sm-row justify-content-between align-items-sm-center gap-2">
            <div>
                <h2 class="h5 fw-bold text-warning-emphasis mb-1"><i class="bi bi-bank me-1"></i> Alertas de cheques</h2>
                <p class="small text-muted mb-0">Cheques en cartera o depositados que vencieron o vencen dentro de los próximos 7 días.</p>
            </div>
            <a href="/cheques/" class="btn btn-sm btn-outline-primary"><i class="bi bi-arrow-up-right"></i> Abrir módulo</a>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead><tr><th>Número</th><th>Banco</th><th>Tipo</th><th>Cliente / proveedor</th><th class="text-end">Monto</th><th>Fecha cobro</th><th>Vencimiento</th><th>Estado</th></tr></thead>
                <tbody>{filas_cheques}</tbody>
            </table>
        </div>
        <div class="card-footer bg-white text-muted small">{len(cheques_alerta)} cheque(s) requieren seguimiento.</div>
    </section>
    """
    return render_layout("Alertas de Stock y Cheques", contenido, seccion_activa="alertas")


# =====================================
# EJECUCIÓN
# =====================================

if __name__ == "__main__":
    app.run(debug=True)