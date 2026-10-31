from flask import Blueprint, request, redirect, url_for, flash, jsonify, session, abort
from decimal import Decimal, InvalidOperation
import html
import json

ventas_bp = Blueprint("ventas", __name__, url_prefix="/ventas")


def _obtener_conexion():
    from app import obtener_conexion
    return obtener_conexion()


def _render(titulo, contenido):
    from app import render_layout
    return render_layout(titulo, contenido, seccion_activa="ventas")


def _asegurar_tablas(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS venta (
            id_venta INT AUTO_INCREMENT PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_empleado INT NOT NULL,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
            condicion_pago VARCHAR(50) NOT NULL DEFAULT 'CONTADO',
            total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
            CONSTRAINT fk_venta_cliente FOREIGN KEY (id_cliente)
                REFERENCES cliente(id_cliente),
            CONSTRAINT fk_venta_empleado FOREIGN KEY (id_empleado)
                REFERENCES empleado(id_empleado)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detalle_venta (
            id_venta INT NOT NULL,
            id_producto INT NOT NULL,
            cantidad INT NOT NULL,
            precio_unitario DECIMAL(12,2) NOT NULL,
            PRIMARY KEY (id_venta, id_producto),
            CONSTRAINT fk_detalle_venta FOREIGN KEY (id_venta)
                REFERENCES venta(id_venta) ON DELETE CASCADE,
            CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto)
                REFERENCES producto(id_producto)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    cursor.execute("""
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'venta'
          AND COLUMN_NAME = 'estado'
    """)
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            ALTER TABLE venta
            ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'COMPLETADA'
        """)


@ventas_bp.route("/")
def listar_ventas():
    conexion = None
    cursor = None
    ventas = []

    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        _asegurar_tablas(cursor)
        conexion.commit()

        filtro_vendedor = "WHERE v.id_empleado = %s" if session.get("rol") == "VENDEDOR" else ""
        parametros = (session.get("id_empleado"),) if filtro_vendedor else ()
        cursor.execute(f"""
                 SELECT v.id_venta,
                   v.fecha,
                     c.nombre,
                     v.condicion_pago,
                   v.total,
                   v.estado,
                     COUNT(d.id_producto) AS total_items
            FROM venta v
                 INNER JOIN cliente c ON c.id_cliente = v.id_cliente
            LEFT JOIN detalle_venta d ON v.id_venta = d.id_venta
              {filtro_vendedor}
                 GROUP BY v.id_venta, v.fecha, c.nombre, v.condicion_pago, v.total, v.estado
            ORDER BY v.id_venta DESC
           """, parametros)
        ventas = cursor.fetchall()
    except Exception as e:
        flash(f"Error al cargar las ventas: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    total_facturado = sum(float(v[4]) for v in ventas if v[5] == "COMPLETADA")
    ventas_completadas = sum(1 for v in ventas if v[5] == "COMPLETADA")

    filas_html = ""
    for v in ventas:
        id_venta = v[0]
        fecha_str = v[1].strftime("%d/%m/%Y %H:%M") if hasattr(v[1], "strftime") else str(v[1])
        cliente = html.escape(str(v[2]))
        metodo = html.escape(str(v[3]))
        total = float(v[4])
        estado = v[5]
        items_count = int(v[6])

        if estado == "COMPLETADA":
            badge_estado = '<span class="badge bg-success-subtle text-success border border-success-subtle"><i class="bi bi-check-circle me-1"></i>Completada</span>'
        else:
            badge_estado = '<span class="badge bg-danger-subtle text-danger border border-danger-subtle"><i class="bi bi-x-circle me-1"></i>Anulada</span>'

        filas_html += f"""
        <tr>
            <td class="font-monospace fw-bold text-primary">#{id_venta:05d}</td>
            <td class="text-secondary small">{fecha_str}</td>
            <td class="fw-semibold text-dark">{cliente}</td>
            <td><span class="badge bg-secondary-subtle text-secondary-emphasis">{metodo}</span></td>
            <td><span class="badge bg-info-subtle text-info-emphasis">{items_count} art.</span></td>
            <td class="font-monospace fw-bold text-dark">${total:,.2f}</td>
            <td>{badge_estado}</td>
            <td class="text-end">
                <div class="btn-group btn-group-sm">
                    <a href="/ventas/comprobante/{id_venta}" class="btn btn-outline-primary" title="Ver Comprobante">
                        <i class="bi bi-receipt"></i> Comprobante
                    </a>
                    {f'''
                    <form action="/ventas/anular/{id_venta}" method="POST" class="d-inline" onsubmit="return confirm('¿Seguro que deseas anular esta venta y devolver el stock al inventario?');">
                        <button type="submit" class="btn btn-outline-danger" title="Anular venta y reponer stock">
                            <i class="bi bi-arrow-counterclockwise"></i> Anular
                        </button>
                    </form>
                    ''' if estado == 'COMPLETADA' and session.get('rol') in {'ADMIN', 'ADMINISTRACION'} else ''}
                </div>
            </td>
        </tr>
        """

    if not ventas:
        filas_html = """
        <tr>
            <td colspan="8" class="text-center text-muted py-5">
                <i class="bi bi-cart-x fs-1 d-block mb-2 text-secondary"></i>
                No se registran ventas realizadas todavía.
            </td>
        </tr>
        """

    contenido = f"""
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <h1 class="h3 fw-bold mb-1">Módulo de Ventas</h1>
            <p class="text-muted mb-0">Facturación, registro de operaciones de mostrador y gestión de comprobantes.</p>
        </div>
        <div class="d-flex gap-2">
            <a href="/" class="btn btn-outline-secondary">
                <i class="bi bi-arrow-left"></i> Panel
            </a>
            {'''<a href="/ventas/nueva" class="btn btn-success shadow-sm">
                <i class="bi bi-cart-plus-fill"></i> Nueva Venta
            </a>''' if session.get("rol") in {"ADMIN", "VENDEDOR"} else ""}
        </div>
    </div>

    <!-- TARJETAS DE RESUMEN -->
    <div class="row g-3 mb-4">
        <div class="col-md-4">
            <div class="card metric-card shadow-sm p-3 h-100" style="border-left-color: #10b981;">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="text-uppercase text-secondary fw-semibold small">Ventas Concretadas</span>
                        <h2 class="h3 fw-bold text-dark mt-1 mb-0">{ventas_completadas}</h2>
                    </div>
                    <div class="bg-success bg-opacity-10 text-success p-3 rounded-circle">
                        <i class="bi bi-cart-check fs-3"></i>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card metric-card shadow-sm p-3 h-100" style="border-left-color: #3b82f6;">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="text-uppercase text-secondary fw-semibold small">Total Facturado</span>
                        <h2 class="h3 fw-bold text-dark mt-1 mb-0">${total_facturado:,.2f}</h2>
                    </div>
                    <div class="bg-primary bg-opacity-10 text-primary p-3 rounded-circle">
                        <i class="bi bi-cash-stack fs-3"></i>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-md-4">
            <div class="card metric-card shadow-sm p-3 h-100" style="border-left-color: #8b5cf6;">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <span class="text-uppercase text-secondary fw-semibold small">Total Registros</span>
                        <h2 class="h3 fw-bold text-dark mt-1 mb-0">{len(ventas)}</h2>
                    </div>
                    <div class="bg-purple bg-opacity-10 text-info p-3 rounded-circle">
                        <i class="bi bi-clock-history fs-3"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="card table-card shadow-sm border-0">
        <div class="card-header bg-white py-3 border-bottom d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2">
            <div class="d-flex align-items-center gap-2">
                <h5 class="fw-bold text-dark mb-0">Historial de Comprobantes</h5>
                <span class="badge bg-primary text-white rounded-pill">{len(ventas)}</span>
            </div>
            <div class="col-md-4">
                <div class="input-group input-group-sm">
                    <span class="input-group-text bg-light border-end-0"><i class="bi bi-search text-muted"></i></span>
                    <input type="text" id="buscadorVentas" class="form-control border-start-0 bg-light" placeholder="Buscar por cliente, ID o condición de pago...">
                </div>
            </div>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0" id="tablaVentas">
                <thead>
                    <tr>
                        <th>Nº Venta</th>
                        <th>Fecha y Hora</th>
                        <th>Cliente</th>
                        <th>Condición de pago</th>
                        <th>Artículos</th>
                        <th>Total</th>
                        <th>Estado</th>
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
            inicializarBuscador('buscadorVentas', 'tablaVentas');
        }});
    </script>
    """
    return _render("Módulo de Ventas", contenido)


@ventas_bp.route("/nueva", methods=["GET", "POST"])
def nueva_venta():
    es_vendedor = session.get("rol") == "VENDEDOR"
    if request.method == "POST":
        try:
            id_cliente = int(request.form.get("id_cliente", ""))
            id_empleado = int(session["id_empleado"]) if es_vendedor else int(request.form.get("id_empleado", ""))
        except ValueError:
            flash("Selecciona un cliente y un vendedor válidos.", "warning")
            return redirect(url_for("ventas.nueva_venta"))

        condicion_pago = request.form.get("condicion_pago", "").strip()
        if condicion_pago not in {"CONTADO", "CUENTA_CORRIENTE"}:
            flash("Selecciona una condición de pago válida.", "warning")
            return redirect(url_for("ventas.nueva_venta"))

        items_json = request.form.get("items_json", "[]")

        try:
            items = json.loads(items_json)
        except Exception:
            flash("Error en el formato de los artículos seleccionados.", "danger")
            return redirect(url_for("ventas.nueva_venta"))

        if not items:
            flash("Debe agregar al menos un producto a la venta.", "warning")
            return redirect(url_for("ventas.nueva_venta"))

        conexion = None
        cursor = None
        try:
            conexion = _obtener_conexion()
            cursor = conexion.cursor()
            _asegurar_tablas(cursor)

            cursor.execute(
                "SELECT id_cliente FROM cliente WHERE id_cliente = %s AND activo = 1",
                (id_cliente,)
            )
            if not cursor.fetchone():
                raise ValueError("El cliente seleccionado no existe o está inactivo.")

            cursor.execute(
                "SELECT id_empleado FROM empleado WHERE id_empleado = %s",
                (id_empleado,)
            )
            if not cursor.fetchone():
                raise ValueError("El vendedor seleccionado no existe.")

            total_venta = Decimal("0.00")
            items_procesados = []

            for item in items:
                codigo = str(item.get("codigo", "")).strip()
                cantidad = int(item.get("cantidad", 0))

                if not codigo or cantidad <= 0:
                    raise ValueError("Cantidad no válida para uno de los artículos.")

                cursor.execute("""
                    SELECT id_producto, nombre, precio_venta, stock_actual
                    FROM producto
                    WHERE codigo = %s AND activo = 1
                    FOR UPDATE
                """, (codigo,))
                prod = cursor.fetchone()

                if not prod:
                    raise ValueError(f"El producto con código '{codigo}' no existe.")

                id_producto = int(prod[0])
                nombre_prod = prod[1]
                precio_unitario = Decimal(str(prod[2]))
                stock_actual = int(prod[3])

                if stock_actual < cantidad:
                    raise ValueError(
                        f"Stock insuficiente para '{nombre_prod}' ({codigo}). "
                        f"Disponible: {stock_actual}, Solicitado: {cantidad}."
                    )

                subtotal = precio_unitario * Decimal(cantidad)
                total_venta += subtotal

                items_procesados.append({
                    "codigo": codigo,
                    "id_producto": id_producto,
                    "nombre": nombre_prod,
                    "cantidad": cantidad,
                    "precio": precio_unitario,
                    "subtotal": subtotal,
                    "nuevo_stock": stock_actual - cantidad
                })

            cursor.execute("""
                INSERT INTO venta
                    (id_cliente, id_empleado, condicion_pago, total, estado)
                VALUES (%s, %s, %s, %s, 'COMPLETADA')
            """, (id_cliente, id_empleado, condicion_pago, total_venta))
            id_venta = cursor.lastrowid

            for it in items_procesados:
                cursor.execute("""
                    INSERT INTO detalle_venta
                        (id_venta, id_producto, cantidad, precio_unitario)
                    VALUES (%s, %s, %s, %s)
                """, (id_venta, it["id_producto"], it["cantidad"], it["precio"]))

                cursor.execute("""
                    UPDATE producto
                    SET stock_actual = %s
                    WHERE id_producto = %s
                """, (it["nuevo_stock"], it["id_producto"]))

            conexion.commit()
            flash(f"¡Venta #{id_venta:05d} registrada exitosamente por ${total_venta:,.2f}!", "success")
            return redirect(url_for("ventas.comprobante", id_venta=id_venta))

        except ValueError as ve:
            if conexion:
                conexion.rollback()
            flash(str(ve), "warning")
            return redirect(url_for("ventas.nueva_venta"))
        except Exception as e:
            if conexion:
                conexion.rollback()
            flash(f"Error procesando la venta: {e}", "danger")
            return redirect(url_for("ventas.nueva_venta"))
        finally:
            if cursor:
                cursor.close()
            if conexion:
                conexion.close()

    productos = []
    clientes = []
    empleados = []
    conexion = None
    cursor = None
    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT codigo, nombre, precio_venta, stock_actual
            FROM producto
            WHERE activo = 1
            ORDER BY nombre
        """)
        productos = cursor.fetchall()

        cursor.execute("SELECT id_cliente, nombre FROM cliente WHERE activo = 1 ORDER BY nombre")
        clientes = cursor.fetchall()

        if es_vendedor:
            empleados = [(session["id_empleado"], session.get("nombre_usuario", "Vendedor"), "VENDEDOR")]
        else:
            cursor.execute("SELECT id_empleado, nombre, rol FROM empleado ORDER BY nombre")
            empleados = cursor.fetchall()
    except Exception as e:
        flash(f"Error al cargar catálogo para venta: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    catalogo_json = json.dumps([
        {
            "codigo": str(p[0]),
            "nombre": str(p[1]),
            "precio": float(p[2]),
            "stock": int(p[3])
        }
        for p in productos
    ])

    clientes_options = '<option value="">Selecciona un cliente...</option>' + "".join(
        f'<option value="{int(c[0])}">{html.escape(str(c[1]))}</option>'
        for c in clientes
    )
    empleados_options = '<option value="">Selecciona un vendedor...</option>' + "".join(
        f'<option value="{int(e[0])}">{html.escape(str(e[1]))} ({html.escape(str(e[2]))})</option>'
        for e in empleados
    )
    if es_vendedor:
        campo_empleado = f'<input type="hidden" name="id_empleado" value="{int(session["id_empleado"])}"><div class="form-control bg-light">{html.escape(str(session.get("nombre_usuario", "Vendedor")))}</div>'
    else:
        campo_empleado = f'<select name="id_empleado" class="form-select" required>{empleados_options}</select>'

    contenido = f"""
    <div class="row justify-content-center">
        <div class="col-xl-11">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div>
                    <h1 class="h3 fw-bold mb-0">Nueva Operación de Venta</h1>
                    <small class="text-muted">Carga de productos y emisión directa de ticket o comprobante.</small>
                </div>
                <a href="/ventas" class="btn btn-outline-secondary">
                    <i class="bi bi-arrow-left"></i> Cancelar y Volver
                </a>
            </div>

            <form id="formVenta" method="POST" action="/ventas/nueva" onsubmit="return prepararEnvio();">
                <input type="hidden" name="items_json" id="itemsJsonInput" value="[]">

                <div class="row g-3">
                    <!-- PANEL IZQUIERDO: DETALLES DE VENTA Y SELECCIÓN -->
                    <div class="col-lg-8">
                        <div class="card shadow-sm border-0 mb-3">
                            <div class="card-header bg-primary text-white py-3">
                                <h5 class="fw-bold mb-0 d-flex align-items-center gap-2">
                                    <i class="bi bi-cart3"></i> Agregar Artículos al Carrito
                                </h5>
                            </div>
                            <div class="card-body p-4">
                                <div class="row g-3 align-items-end">
                                    <div class="col-md-7">
                                        <label for="busquedaProducto" class="form-label fw-semibold text-secondary">Buscar producto por código o nombre:</label>
                                        <div class="position-relative">
                                            <input id="busquedaProducto" type="search" class="form-control" placeholder="Escribe un código o nombre..." autocomplete="off" role="combobox" aria-autocomplete="list" aria-controls="resultadosProductos" aria-expanded="false">
                                            <div id="resultadosProductos" class="list-group position-absolute top-100 start-0 w-100 shadow d-none" role="listbox" style="z-index: 20; max-height: 18rem; overflow-y: auto;"></div>
                                        </div>
                                        <small id="estadoBusquedaProducto" class="form-text text-muted" aria-live="polite">Empieza a escribir para ver coincidencias.</small>
                                    </div>
                                    <div class="col-md-2 col-6">
                                        <label class="form-label fw-semibold text-secondary">Cantidad:</label>
                                        <input type="number" id="inputCantidad" class="form-control" value="1" min="1" step="1">
                                    </div>
                                    <div class="col-md-3 col-6">
                                        <button type="button" class="btn btn-success w-100" onclick="agregarAlCarrito()">
                                            <i class="bi bi-plus-circle-fill"></i> Agregar
                                        </button>
                                    </div>
                                </div>

                                <div id="infoProductoSeleccionado" class="mt-3 p-3 bg-light rounded border d-none">
                                    <div class="d-flex justify-content-between align-items-center small">
                                        <div>
                                            <span class="text-secondary">Precio Unitario:</span>
                                            <strong class="text-dark font-monospace fs-6" id="infoPrecio">$0.00</strong>
                                        </div>
                                        <div>
                                            <span class="text-secondary">Stock Disponible:</span>
                                            <strong class="font-monospace fs-6" id="infoStock">0 u.</strong>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- TABLA DE ARTÍCULOS EN CARRITO -->
                        <div class="card shadow-sm border-0 table-card">
                            <div class="card-header bg-white py-3 border-bottom d-flex justify-content-between align-items-center">
                                <h6 class="fw-bold mb-0 text-dark">
                                    <i class="bi bi-list-check"></i> Detalle de Artículos a Facturar
                                </h6>
                                <button type="button" class="btn btn-outline-danger btn-sm" onclick="vaciarCarrito()">
                                    <i class="bi bi-trash"></i> Vaciar Carrito
                                </button>
                            </div>
                            <div class="table-responsive">
                                <table class="table table-hover align-middle mb-0" id="tablaCarrito">
                                    <thead>
                                        <tr>
                                            <th>Código</th>
                                            <th>Descripción</th>
                                            <th class="text-center" style="width: 110px;">Cant.</th>
                                            <th>Precio Unit.</th>
                                            <th>Subtotal</th>
                                            <th class="text-end" style="width: 60px;"></th>
                                        </tr>
                                    </thead>
                                    <tbody id="carritoTbody">
                                        <tr>
                                            <td colspan="6" class="text-center text-muted py-4">
                                                No hay artículos agregados todavía.
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <!-- PANEL DERECHO: TOTALES Y CONFIRMACIÓN -->
                    <div class="col-lg-4">
                        <div class="card shadow-sm border-0 sticky-top" style="top: 85px;">
                            <div class="card-header bg-dark text-white py-3">
                                <h5 class="fw-bold mb-0 d-flex align-items-center gap-2">
                                    <i class="bi bi-cash-coin"></i> Resumen de Venta
                                </h5>
                            </div>
                            <div class="card-body p-4">
                                <div class="mb-3">
                                    <label class="form-label fw-semibold text-secondary">Cliente (*):</label>
                                    <select name="id_cliente" class="form-select" required>
                                        {clientes_options}
                                    </select>
                                </div>

                                <div class="mb-3">
                                    <label class="form-label fw-semibold text-secondary">Vendedor (*):</label>
                                    {campo_empleado}
                                </div>

                                <div class="mb-3">
                                    <label class="form-label fw-semibold text-secondary">Condición de pago (*):</label>
                                    <select name="condicion_pago" class="form-select" required>
                                        <option value="CONTADO" selected>Contado</option>
                                        <option value="CUENTA_CORRIENTE">Cuenta corriente</option>
                                    </select>
                                </div>

                                <hr>

                                <div class="d-flex justify-content-between align-items-center mb-2">
                                    <span class="text-secondary">Cant. de Ítems:</span>
                                    <strong id="resumenTotalItems" class="font-monospace">0</strong>
                                </div>

                                <div class="d-flex justify-content-between align-items-center mb-4">
                                    <span class="fs-5 fw-bold text-dark">TOTAL:</span>
                                    <span class="fs-3 fw-bolder text-primary font-monospace" id="resumenTotalPrecio">$0.00</span>
                                </div>

                                <button type="submit" id="btnConfirmarVenta" class="btn btn-success btn-lg w-100 shadow-sm" disabled>
                                    <i class="bi bi-check-circle-fill"></i> Registrar y Emitir Venta
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </form>
        </div>
    </div>

    <script>
        const catalogo = {catalogo_json};
        let carrito = [];
        let productoSeleccionado = null;

        document.addEventListener('DOMContentLoaded', () => {{
            const busqueda = document.getElementById('busquedaProducto');
            const resultados = document.getElementById('resultadosProductos');

            busqueda.addEventListener('input', renderizarCoincidencias);
            busqueda.addEventListener('focus', renderizarCoincidencias);
            busqueda.addEventListener('keydown', event => {{
                if (event.key === 'Escape') {{
                    ocultarCoincidencias();
                }} else if (event.key === 'Enter' && !resultados.classList.contains('d-none')) {{
                    const primeraCoincidencia = resultados.querySelector('[role="option"]');
                    if (primeraCoincidencia) {{
                        event.preventDefault();
                        seleccionarProducto(primeraCoincidencia.dataset.codigo);
                    }}
                }}
            }});

            document.addEventListener('click', event => {{
                if (!event.target.closest('#busquedaProducto') && !event.target.closest('#resultadosProductos')) {{
                    ocultarCoincidencias();
                }}
            }});
        }});

        function normalizarBusqueda(texto) {{
            return texto.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
        }}

        function ocultarCoincidencias() {{
            const resultados = document.getElementById('resultadosProductos');
            resultados.classList.add('d-none');
            document.getElementById('busquedaProducto').setAttribute('aria-expanded', 'false');
        }}

        function renderizarCoincidencias() {{
            const busqueda = document.getElementById('busquedaProducto');
            const resultados = document.getElementById('resultadosProductos');
            const estado = document.getElementById('estadoBusquedaProducto');
            const consulta = normalizarBusqueda(busqueda.value.trim());

            resultados.replaceChildren();
            productoSeleccionado = null;
            document.getElementById('infoProductoSeleccionado').classList.add('d-none');

            if (!consulta) {{
                ocultarCoincidencias();
                estado.textContent = 'Empieza a escribir para ver coincidencias.';
                return;
            }}

            const totalCoincidencias = catalogo.filter(producto =>
                normalizarBusqueda(`${{producto.codigo}} ${{producto.nombre}}`).includes(consulta)
            ).length;
            const coincidencias = catalogo.filter(producto =>
                normalizarBusqueda(`${{producto.codigo}} ${{producto.nombre}}`).includes(consulta)
            ).slice(0, 12);

            if (!coincidencias.length) {{
                const sinResultados = document.createElement('div');
                sinResultados.className = 'list-group-item text-muted';
                sinResultados.textContent = 'No se encontraron productos.';
                resultados.appendChild(sinResultados);
                estado.textContent = 'Sin coincidencias.';
            }} else {{
                coincidencias.forEach(producto => {{
                    const opcion = document.createElement('button');
                    opcion.type = 'button';
                    opcion.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center gap-3';
                    opcion.setAttribute('role', 'option');
                    opcion.dataset.codigo = producto.codigo;

                    const descripcion = document.createElement('span');
                    descripcion.className = 'text-start';
                    descripcion.textContent = `${{producto.codigo}} - ${{producto.nombre}}`;

                    const datos = document.createElement('span');
                    datos.className = 'text-end text-nowrap small text-muted';
                    datos.textContent = `$${{producto.precio.toFixed(2)}} · Stock: ${{producto.stock}}`;

                    opcion.append(descripcion, datos);
                    opcion.addEventListener('click', () => seleccionarProducto(producto.codigo));
                    resultados.appendChild(opcion);
                }});
                estado.textContent = `${{totalCoincidencias}} coincidencia${{totalCoincidencias === 1 ? '' : 's'}}${{totalCoincidencias > 12 ? ' (muestra las primeras 12)' : ''}}.`;
            }}

            resultados.classList.remove('d-none');
            busqueda.setAttribute('aria-expanded', 'true');
        }}

        function seleccionarProducto(codigo) {{
            productoSeleccionado = catalogo.find(producto => producto.codigo === codigo) || null;
            if (!productoSeleccionado) return;

            const busqueda = document.getElementById('busquedaProducto');
            busqueda.value = `${{productoSeleccionado.codigo}} - ${{productoSeleccionado.nombre}}`;
            ocultarCoincidencias();

            const infoBox = document.getElementById('infoProductoSeleccionado');
            const infoPrecio = document.getElementById('infoPrecio');
            const infoStock = document.getElementById('infoStock');
            const inputCantidad = document.getElementById('inputCantidad');
            infoPrecio.textContent = '$' + productoSeleccionado.precio.toLocaleString('es-AR', {{minimumFractionDigits: 2}});
            infoStock.textContent = productoSeleccionado.stock + ' u.';
            infoStock.className = productoSeleccionado.stock > 0 ? 'text-success font-monospace fs-6' : 'text-danger font-monospace fs-6';
            inputCantidad.max = productoSeleccionado.stock;
            infoBox.classList.remove('d-none');
            inputCantidad.focus();
        }}

        function agregarAlCarrito() {{
            const prod = productoSeleccionado;
            const cantidad = parseInt(document.getElementById('inputCantidad').value) || 0;

            if (!prod) {{
                alert('Por favor selecciona un producto.');
                return;
            }}

            const codigo = prod.codigo;

            if (prod.stock <= 0) {{
                alert('El producto seleccionado no tiene stock disponible.');
                return;
            }}

            const itemExistente = carrito.find(it => it.codigo === codigo);
            const cantTotal = (itemExistente ? itemExistente.cantidad : 0) + cantidad;

            if (cantTotal > prod.stock) {{
                alert(`No hay stock suficiente. Stock máximo disponible: ${{prod.stock}} u.`);
                return;
            }}

            if (itemExistente) {{
                itemExistente.cantidad = cantTotal;
                itemExistente.subtotal = itemExistente.cantidad * itemExistente.precio;
            }} else {{
                carrito.push({{
                    codigo: prod.codigo,
                    nombre: prod.nombre,
                    precio: prod.precio,
                    cantidad: cantidad,
                    subtotal: cantidad * prod.precio
                }});
            }}

            document.getElementById('busquedaProducto').value = '';
            productoSeleccionado = null;
            document.getElementById('inputCantidad').value = 1;
            document.getElementById('infoProductoSeleccionado').classList.add('d-none');
            renderizarCarrito();
        }}

        function actualizarCantidadItem(codigo, nuevaCant) {{
            const item = carrito.find(it => it.codigo === codigo);
            const prod = catalogo.find(p => p.codigo === codigo);
            if (!item || !prod) return;

            nuevaCant = parseInt(nuevaCant) || 1;
            if (nuevaCant <= 0) nuevaCant = 1;

            if (nuevaCant > prod.stock) {{
                alert(`Stock máximo disponible: ${{prod.stock}} u.`);
                nuevaCant = prod.stock;
            }}

            item.cantidad = nuevaCant;
            item.subtotal = item.cantidad * item.precio;
            renderizarCarrito();
        }}

        function eliminarDelCarrito(codigo) {{
            carrito = carrito.filter(it => it.codigo !== codigo);
            renderizarCarrito();
        }}

        function vaciarCarrito() {{
            if (carrito.length === 0) return;
            if (confirm('¿Vaciar todos los artículos del carrito?')) {{
                carrito = [];
                renderizarCarrito();
            }}
        }}

        function renderizarCarrito() {{
            const tbody = document.getElementById('carritoTbody');
            const resumenItems = document.getElementById('resumenTotalItems');
            const resumenTotal = document.getElementById('resumenTotalPrecio');
            const btnConfirmar = document.getElementById('btnConfirmarVenta');

            if (carrito.length === 0) {{
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" class="text-center text-muted py-4">
                            No hay artículos agregados todavía.
                        </td>
                    </tr>
                `;
                resumenItems.textContent = '0';
                resumenTotal.textContent = '$0.00';
                btnConfirmar.disabled = true;
                return;
            }}

            let total = 0;
            let totalUnidades = 0;
            let htmlFilas = '';

            carrito.forEach(it => {{
                total += it.subtotal;
                totalUnidades += it.cantidad;
                htmlFilas += `
                    <tr>
                        <td class="font-monospace fw-bold text-primary">${{it.codigo}}</td>
                        <td class="fw-semibold text-dark">${{it.nombre}}</td>
                        <td class="text-center">
                            <input type="number" min="1" class="form-control form-control-sm text-center"
                                   value="${{it.cantidad}}" onchange="actualizarCantidadItem('${{it.codigo}}', this.value)">
                        </td>
                        <td class="font-monospace">$${{it.precio.toFixed(2)}}</td>
                        <td class="font-monospace fw-bold text-dark">$${{it.subtotal.toFixed(2)}}</td>
                        <td class="text-end">
                            <button type="button" class="btn btn-outline-danger btn-sm p-1" onclick="eliminarDelCarrito('${{it.codigo}}')">
                                <i class="bi bi-x-lg"></i>
                            </button>
                        </td>
                    </tr>
                `;
            }});

            tbody.innerHTML = htmlFilas;
            resumenItems.textContent = totalUnidades;
            resumenTotal.textContent = '$' + total.toLocaleString('es-AR', {{minimumFractionDigits: 2}});
            btnConfirmar.disabled = false;
        }}

        function prepararEnvio() {{
            if (carrito.length === 0) {{
                alert('Debe agregar al menos un artículo a la venta.');
                return false;
            }}
            document.getElementById('itemsJsonInput').value = JSON.stringify(carrito);
            return true;
        }}
    </script>
    """
    return _render("Nueva Venta", contenido)


@ventas_bp.route("/comprobante/<int:id_venta>")
def comprobante(id_venta):
    conexion = None
    cursor = None
    venta = None
    detalles = []
    acceso_denegado = False

    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        _asegurar_tablas(cursor)

        cursor.execute("""
            SELECT v.id_venta,
                   v.fecha,
                   c.nombre,
                   v.condicion_pago,
                   v.total,
                   v.estado,
                   v.id_empleado
            FROM venta AS v
            INNER JOIN cliente AS c ON c.id_cliente = v.id_cliente
            WHERE v.id_venta = %s
        """, (id_venta,))
        venta = cursor.fetchone()
        if venta and session.get("rol") == "VENDEDOR" and int(venta[6]) != int(session["id_empleado"]):
            acceso_denegado = True

        if venta and not acceso_denegado:
            cursor.execute("""
                SELECT p.codigo,
                       p.nombre,
                       d.cantidad,
                       d.precio_unitario,
                       d.cantidad * d.precio_unitario AS subtotal
                FROM detalle_venta AS d
                INNER JOIN producto AS p ON p.id_producto = d.id_producto
                WHERE d.id_venta = %s
                ORDER BY d.id_producto ASC
            """, (id_venta,))
            detalles = cursor.fetchall()
    except Exception as e:
        flash(f"Error al obtener el comprobante: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    if acceso_denegado:
        abort(403)

    if not venta:
        flash(f"No se encontró el comprobante para la venta #{id_venta}.", "warning")
        return redirect(url_for("ventas.listar_ventas"))

    fecha_str = venta[1].strftime("%d/%m/%Y %H:%M:%S") if hasattr(venta[1], "strftime") else str(venta[1])
    cliente = html.escape(str(venta[2]))
    condicion_pago = html.escape(str(venta[3]))
    total = float(venta[4])
    estado = venta[5]

    filas_detalles = ""
    for d in detalles:
        cod = html.escape(str(d[0]))
        nom = html.escape(str(d[1]))
        cant = int(d[2])
        precio_u = float(d[3])
        sub = float(d[4])

        filas_detalles += f"""
        <tr>
            <td class="font-monospace text-primary fw-bold">{cod}</td>
            <td class="fw-semibold text-dark">{nom}</td>
            <td class="text-center font-monospace">{cant}</td>
            <td class="text-end font-monospace">${precio_u:,.2f}</td>
            <td class="text-end font-monospace fw-bold">${sub:,.2f}</td>
        </tr>
        """

    contenido = f"""
    <div class="row justify-content-center">
        <div class="col-lg-8 col-md-10">
            <!-- BOTONES DE ACCIÓN SUPERIOR -->
            <div class="d-flex justify-content-between align-items-center mb-3 d-print-none">
                <a href="/ventas" class="btn btn-outline-secondary">
                    <i class="bi bi-arrow-left"></i> Volver a Ventas
                </a>
                <div class="d-flex gap-2">
                    {'''<a href="/ventas/nueva" class="btn btn-success">
                        <i class="bi bi-plus-lg"></i> Nueva Venta
                    </a>''' if session.get("rol") in {"ADMIN", "VENDEDOR"} else ""}
                    <button type="button" class="btn btn-primary" onclick="window.print()">
                        <i class="bi bi-printer-fill"></i> Imprimir Ticket
                    </button>
                </div>
            </div>

            <!-- TICKET / COMPROBANTE FACTURA -->
            <div class="card shadow border-0 p-4 bg-white" id="comprobanteImprimible">
                <div class="row border-bottom pb-3 mb-3">
                    <div class="col-sm-6">
                        <h4 class="fw-bold mb-0 text-dark">🔨 Ferretería CANJER</h4>
                        <small class="text-muted d-block">Suministros Industriales y del Hogar</small>
                        <small class="text-muted d-block">CUIT: 30-71982341-9 &bull; IVA Responsable Inscripto</small>
                        <small class="text-muted">Av. San Martín 1540, Buenos Aires</small>
                    </div>
                    <div class="col-sm-6 text-sm-end mt-3 mt-sm-0">
                        <span class="badge {'bg-success' if estado == 'COMPLETADA' else 'bg-danger'} fs-6 px-3 py-2 mb-2">
                            {estado}
                        </span>
                        <h5 class="fw-bold text-primary font-monospace mb-0">COMPROBANTE #{id_venta:05d}</h5>
                        <small class="text-secondary d-block">Fecha: {fecha_str}</small>
                    </div>
                </div>

                <div class="row mb-4">
                    <div class="col-sm-6">
                        <span class="text-secondary small fw-semibold text-uppercase">Datos del Cliente</span>
                        <div class="fw-bold fs-6 text-dark">{cliente}</div>
                    </div>
                    <div class="col-sm-6 text-sm-end mt-2 mt-sm-0">
                        <span class="text-secondary small fw-semibold text-uppercase">Forma de Pago</span>
                        <div class="fw-semibold text-dark">{condicion_pago}</div>
                    </div>
                </div>

                <div class="table-responsive mb-4">
                    <table class="table table-sm table-bordered align-middle mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>Cód.</th>
                                <th>Descripción</th>
                                <th class="text-center">Cant.</th>
                                <th class="text-end">Precio Unit.</th>
                                <th class="text-end">Subtotal</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filas_detalles}
                        </tbody>
                        <tfoot>
                            <tr>
                                <th colspan="4" class="text-end fs-5 py-2">TOTAL:</th>
                                <th class="text-end fs-5 text-primary py-2 font-monospace">${total:,.2f}</th>
                            </tr>
                        </tfoot>
                    </table>
                </div>

                <div class="text-center text-muted small border-top pt-3">
                    <p class="mb-0">¡Gracias por su compra en Ferretería CANJER!</p>
                    <p class="mb-0">Documento de control interno no válido como factura fiscal.</p>
                </div>
            </div>
        </div>
    </div>

    <style>
        @media print {{
            .navbar, footer, .d-print-none {{
                display: none !important;
            }}
            body {{
                background-color: #ffffff !important;
            }}
            .card {{
                box-shadow: none !important;
                border: none !important;
            }}
        }}
    </style>
    """
    return _render(f"Comprobante #{id_venta:05d}", contenido)


@ventas_bp.route("/anular/<int:id_venta>", methods=["POST"])
def anular_venta(id_venta):
    conexion = None
    cursor = None
    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        _asegurar_tablas(cursor)

        cursor.execute("SELECT estado FROM venta WHERE id_venta = %s FOR UPDATE", (id_venta,))
        fila = cursor.fetchone()

        if not fila:
            flash(f"La venta #{id_venta} no existe.", "danger")
            return redirect(url_for("ventas.listar_ventas"))

        if fila[0] == "ANULADA":
            flash(f"La venta #{id_venta} ya se encuentra anulada.", "warning")
            return redirect(url_for("ventas.listar_ventas"))

        cursor.execute("""
            SELECT id_producto, cantidad
            FROM detalle_venta
            WHERE id_venta = %s
        """, (id_venta,))
        detalles = cursor.fetchall()

        for id_producto, cant in detalles:
            cursor.execute("""
                UPDATE producto
                SET stock_actual = stock_actual + %s
                WHERE id_producto = %s
            """, (cant, id_producto))

        cursor.execute("UPDATE venta SET estado = 'ANULADA' WHERE id_venta = %s", (id_venta,))
        conexion.commit()
        flash(f"Venta #{id_venta:05d} anulada correctamente y stock reincorporado al catálogo.", "success")
    except Exception as e:
        if conexion:
            conexion.rollback()
        flash(f"Error al anular la venta: {e}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    return redirect(url_for("ventas.listar_ventas"))