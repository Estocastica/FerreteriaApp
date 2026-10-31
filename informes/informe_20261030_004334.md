Como arquitecto de software, antes de implementar el nuevo módulo es fundamental realizar un **diagnóstico técnico** del estado actual del código, ya que presenta varios antipatrones críticos que afectarán la escalabilidad, estabilidad y seguridad del sistema.

---

### 1. Diagnóstico y Hallazgos Críticos

1. **Conexión global compartida a MySQL (`conexion = mysql.connector.connect(...)`):**
   * **Problema:** Se abre una única conexión al iniciar el script. MySQL cierra las conexiones inactivas tras un tiempo (`wait_timeout`), lo que provocará errores de tipo `MySQL Connection not available` o `Lost connection to MySQL server`. Además, Flask es multihilo en entornos reales: compartir un único objeto de conexión/cursor entre múltiples peticiones causará colisiones de transacciones y estados corruptos.
   * **Solución:** Implementar un **Pool de Conexiones** (`mysql.connector.pooling`) o gestionar la apertura/cierre por ciclo de vida de la petición (`g` de Flask con `teardown_appcontext`).

2. **Falta de cierre de cursores:**
   * **Problema:** En ninguna ruta se cierran los cursores (`cursor.close()`). Esto genera fugas de memoria y bloqueos en el servidor de base de datos por cursores zombies.

3. **Inyección directa de HTML (XSS y acoplamiento):**
   * **Problema:** Concatenar variables directamente en strings HTML (`f"<td>{fila[0]}</td>"`) abre una brecha de seguridad grave de **Cross-Site Scripting (XSS)** si los datos provienen de inputs no saneados.
   * **Solución ideal:** Usar plantillas Jinja2 (`templates/`). Sin embargo, para mantener coherencia con la estructura actual sin obligarte a reescribir todo el proyecto de golpe, encapsularemos el módulo de forma segura y modular.

4. **Monolito en un solo archivo:**
   * **Problema:** Todo el código reside en `app.py`. A medida que el negocio crezca (compras, ventas, proveedores, reportes), el archivo se volverá inmantenible.
   * **Solución arquitectónica:** Usar **Flask Blueprints** para separar los módulos en archivos independientes.

---

### 2. Estructura de la Base de Datos (DDL)

Para que el módulo de proveedores funcione, ejecuta esta sentencia SQL en tu base de datos `ferreteria`:

```sql
CREATE TABLE IF NOT EXISTS proveedor (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cuit VARCHAR(20) NOT NULL UNIQUE,
    razon_social VARCHAR(150) NOT NULL,
    contacto VARCHAR(100),
    telefono VARCHAR(50),
    email VARCHAR(100),
    direccion VARCHAR(200),
    activo TINYINT(1) DEFAULT 1,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Datos de prueba
INSERT INTO proveedor (cuit, razon_social, contacto, telefono, email, direccion) VALUES
('30-71123456-8', 'Distribuidora Bulonera S.A.', 'Carlos Pérez', '11-4567-8901', 'ventas@bulonera.com', 'Av. Industrial 1234'),
('30-65987412-3', 'Herramientas del Sur S.R.L.', 'Mariana Gómez', '11-3214-5678', 'mgomez@herramientasur.com', 'Ruta 8 Km 45');
```

---

### 3. Código del Módulo: `proveedores.py`

Crea este archivo en la raíz de tu proyecto. Utiliza `Blueprint` de Flask, maneja listado, alta rápida vía formulario modal de Bootstrap 5, validación de datos, control de excepciones y liberación de recursos.

```python
"""
Módulo: proveedores.py
Descripción: Gestión de proveedores de Ferretería CANJER.
Arquitectura: Flask Blueprint con Bootstrap 5 y MySQL Connector.
"""

from flask import Blueprint, request, redirect, url_for, flash
import html

# Creamos el Blueprint para desacoplar el módulo del archivo principal
proveedores_bp = Blueprint('proveedores', __name__, url_prefix='/proveedores')

def obtener_conexion():
    """
    Importa la conexión centralizada desde app.py de manera segura
    o resuelve una conexión del pool.
    """
    from app import db_pool
    return db_pool.get_connection()


@proveedores_bp.route('/', methods=['GET'])
def listar():
    conexion = None
    cursor = None
    filas = []

    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("""
            SELECT id,
                   cuit,
                   razon_social,
                   contacto,
                   telefono,
                   email,
                   direccion,
                   activo
            FROM proveedor
            ORDER BY razon_social ASC
        """)
        filas = cursor.fetchall()
    except Exception as e:
        print(f"❌ Error al consultar proveedores: {e}")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()  # Se devuelve al pool

    # Construcción segura de la vista con Bootstrap 5
    filas_html = ""
    for f in filas:
        estado_badge = '<span class="badge bg-success">Activo</span>' if f['activo'] else '<span class="badge bg-danger">Inactivo</span>'
        filas_html += f"""
        <tr>
            <td class="fw-bold">{html.escape(str(f['cuit']))}</td>
            <td>{html.escape(str(f['razon_social']))}</td>
            <td>{html.escape(str(f['contacto'] or '-'))}</td>
            <td>{html.escape(str(f['telefono'] or '-'))}</td>
            <td>{html.escape(str(f['email'] or '-'))}</td>
            <td>{html.escape(str(f['direccion'] or '-'))}</td>
            <td class="text-center">{estado_badge}</td>
        </tr>
        """

    if not filas:
        filas_html = """
        <tr>
            <td colspan="7" class="text-center text-muted py-4">
                No hay proveedores registrados.
            </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Proveedores - Ferretería CANJER</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container mt-4 mb-5">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <a href="/" class="btn btn-secondary">
                    🏠 Volver al menú
                </a>
                <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#modalNuevoProveedor">
                    ➕ Nuevo Proveedor
                </button>
            </div>

            <div class="card shadow-sm border-0">
                <div class="card-header bg-dark text-white d-flex align-items-center">
                    <h2 class="h4 mb-0">🚚 Directorio de Proveedores</h2>
                </div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-striped table-hover mb-0 align-middle">
                            <thead class="table-secondary">
                                <tr>
                                    <th>CUIT</th>
                                    <th>Razón Social</th>
                                    <th>Contacto</th>
                                    <th>Teléfono</th>
                                    <th>Email</th>
                                    <th>Dirección</th>
                                    <th class="text-center">Estado</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filas_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modal Alta de Proveedor -->
        <div class="modal fade" id="modalNuevoProveedor" tabindex="-1" aria-labelledby="modalLabel" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <form action="/proveedores/nuevo" method="POST">
                        <div class="modal-header bg-primary text-white">
                            <h5 class="modal-title" id="modalLabel">Registrar Nuevo Proveedor</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label">CUIT (*):</label>
                                <input type="text" name="cuit" class="form-control" placeholder="XX-XXXXXXXX-X" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Razón Social (*):</label>
                                <input type="text" name="razon_social" class="form-control" placeholder="Nombre comercial / fiscal" required>
                            </div>
                            <div class="row">
                                <div class="col-md-6 mb-3">
                                    <label class="form-label">Contacto:</label>
                                    <input type="text" name="contacto" class="form-control" placeholder="Persona de contacto">
                                </div>
                                <div class="col-md-6 mb-3">
                                    <label class="form-label">Teléfono:</label>
                                    <input type="text" name="telefono" class="form-control" placeholder="Ej: 11-1234-5678">
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Email:</label>
                                <input type="email" name="email" class="form-control" placeholder="correo@proveedor.com">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Dirección:</label>
                                <input type="text" name="direccion" class="form-control" placeholder="Calle, Altura, Localidad">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                            <button type="submit" class="btn btn-primary">Guardar Proveedor</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """


@proveedores_bp.route('/nuevo', methods=['POST'])
def nuevo():
    """Procesa el alta de un proveedor mediante consulta parametrizada contra SQLi."""
    cuit = request.form.get('cuit', '').strip()
    razon_social = request.form.get('razon_social', '').strip()
    contacto = request.form.get('contacto', '').strip()
    telefono = request.form.get('telefono', '').strip()
    email = request.form.get('email', '').strip()
    direccion = request.form.get('direccion', '').strip()

    if not cuit or not razon_social:
        return redirect(url_for('proveedores.listar'))

    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        query = """
            INSERT INTO proveedor (cuit, razon_social, contacto, telefono, email, direccion)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (cuit, razon_social, contacto, telefono, email, direccion))
        conexion.commit()
    except Exception as e:
        if conexion:
            conexion.rollback()
        print(f"❌ Error al registrar proveedor: {e}")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    return redirect(url_for('proveedores.listar'))
```

---

### 4. Código Completo de `app.py` (Actualizado y Refactorizado)

Se actualiza `app.py` integrando:
1. **Pool de conexiones** (`MySQLConnectionPool`), solucionando los problemas de concurrencia y timeouts.
2. **Registro del Blueprint** de proveedores.
3. **Acceso al módulo de proveedores** en el menú principal.
4. Uso correcto de cierre de cursores y conexiones en todas las rutas existentes.

```python
"""
Archivo: app.py
Aplicación principal Ferretería CANJER.
Refactorizado con Connection Pooling y arquitectura modular con Blueprints.
"""

from flask import Flask
from mysql.connector import pooling
import html

app = Flask(__name__)
app.secret_key = "ferreteria_secret_key_prod"

# =====================================
# POOL DE CONEXIONES A MYSQL
# =====================================

db_config = {
    "host": "localhost",
    "port": 3307,
    "user": "root",
    "password": "1234",
    "database": "ferreteria"
}

try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="ferreteria_pool",
        pool_size=5,
        pool_reset_session=True,
        **db_config
    )
    print("✅ Pool de conexiones a MySQL iniciado correctamente")
except Exception as e:
    print(f"❌ Error al iniciar el pool de conexiones: {e}")
    db_pool = None

# =====================================
# REGISTRO DE BLUEPRINTS (MÓDULOS)
# =====================================

from proveedores import proveedores_bp
app.register_blueprint(proveedores_bp)


# =====================================
# MENÚ PRINCIPAL
# =====================================

@app.route("/")
def inicio():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Ferretería CANJER</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container mt-5">
            <div class="card shadow">
                <div class="card-header bg-primary text-white">
                    <h1>🔨 Ferretería CANJER</h1>
                </div>
                <div class="card-body">
                    <h3>Menú Principal</h3>
                    <hr>
                    <div class="d-flex flex-wrap gap-2">
                        <a href="/productos" class="btn btn-primary btn-lg">
                            📦 Productos
                        </a>
                        <a href="/clientes" class="btn btn-success btn-lg">
                            👥 Clientes
                        </a>
                        <a href="/proveedores" class="btn btn-info text-white btn-lg">
                            🚚 Proveedores
                        </a>
                        <a href="/alertas" class="btn btn-warning btn-lg">
                            ⚠ Alertas
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


# =====================================
# PRODUCTOS
# =====================================

@app.route("/productos")
def productos():
    conexion = None
    cursor = None
    filas = []

    try:
        conexion = db_pool.get_connection()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT codigo,
                   nombre,
                   precio_venta,
                   stock_actual
            FROM producto
            ORDER BY nombre
        """)
        filas = cursor.fetchall()
    except Exception as e:
        print("❌ Error en productos:", e)
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    filas_html = ""
    for fila in filas:
        filas_html += f"""
        <tr>
            <td>{html.escape(str(fila[0]))}</td>
            <td>{html.escape(str(fila[1]))}</td>
            <td>${html.escape(str(fila[2]))}</td>
            <td>{html.escape(str(fila[3]))}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Productos</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container mt-4">
            <a href="/" class="btn btn-secondary mb-3">🏠 Volver al menú</a>
            <h1>📦 Productos</h1>
            <table class="table table-striped table-hover shadow-sm">
                <thead class="table-dark">
                    <tr>
                        <th>Código</th>
                        <th>Producto</th>
                        <th>Precio</th>
                        <th>Stock</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


# =====================================
# CLIENTES
# =====================================

@app.route("/clientes")
def clientes():
    conexion = None
    cursor = None
    filas = []

    try:
        conexion = db_pool.get_connection()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT nombre,
                   tipo,
                   limite_credito
            FROM cliente
            ORDER BY nombre
        """)
        filas = cursor.fetchall()
    except Exception as e:
        print("❌ Error en clientes:", e)
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    filas_html = ""
    for fila in filas:
        filas_html += f"""
        <tr>
            <td>{html.escape(str(fila[0]))}</td>
            <td>{html.escape(str(fila[1]))}</td>
            <td>${html.escape(str(fila[2]))}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Clientes</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container mt-4">
            <a href="/" class="btn btn-secondary mb-3">🏠 Volver al menú</a>
            <h1>👥 Clientes</h1>
            <table class="table table-striped table-hover shadow-sm">
                <thead class="table-dark">
                    <tr>
                        <th>Nombre</th>
                        <th>Tipo</th>
                        <th>Límite Crédito</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


# =====================================
# ALERTAS
# =====================================

@app.route("/alertas")
def alertas():
    conexion = None
    cursor = None
    filas = []

    try:
        conexion = db_pool.get_connection()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT codigo,
                   producto,
                   stock_actual,
                   stock_minimo
            FROM v_stock_a_reponer
        """)
        filas = cursor.fetchall()
    except Exception as e:
        print("❌ Error en alertas:", e)
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    filas_html = ""
    for fila in filas:
        filas_html += f"""
        <tr>
            <td>{html.escape(str(fila[0]))}</td>
            <td>{html.escape(str(fila[1]))}</td>
            <td>{html.escape(str(fila[2]))}</td>
            <td>{html.escape(str(fila[3]))}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Alertas</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
        <div class="container mt-4">
            <a href="/" class="btn btn-secondary mb-3">🏠 Volver al menú</a>
            <h1>⚠ Productos a Reponer</h1>
            <table class="table table-striped table-hover shadow-sm">
                <thead class="table-danger">
                    <tr>
                        <th>Código</th>
                        <th>Producto</th>
                        <th>Stock</th>
                        <th>Mínimo</th>
                    </tr>
                </thead>
                <tbody>
                    {filas_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


# =====================================
# EJECUCIÓN
# =====================================

if __name__ == "__main__":
    app.run(debug=True)
```

---

### 5. Resumen de Beneficios de la Solución

1. **Escalabilidad modular:** El código de Proveedores vive de forma independiente en `proveedores.py`. Si necesitas agregar edición, eliminación o vinculación con compras de stock, se hace allí sin tocar `app.py`.
2. **Resiliencia en base de datos:** Se adoptó `MySQLConnectionPool`. Cada petición adquiere una conexión y la libera al finalizar (`finally`), eliminando los cuellos de botella y caídas por timeout.
3. **Seguridad reforzada:** Se introdujo `html.escape()` contra XSS en los renders y consultas SQL parametrizadas (`%s`) en la creación de registros contra ataques de inyección SQL (SQLi).
4. **Experiencia de usuario (UX):** El módulo incluye una interfaz Bootstrap 5 con modal interactivo para crear nuevos proveedores sin recargar páginas intermedias.