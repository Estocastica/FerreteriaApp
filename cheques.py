import html
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, request, url_for, session


cheques_bp = Blueprint("cheques", __name__, url_prefix="/cheques")
ESTADOS_CHEQUE = {"EN_CARTERA", "DEPOSITADO", "COBRADO", "RECHAZADO"}
ESTADOS_PENDIENTES = ("EN_CARTERA", "DEPOSITADO")


def _obtener_conexion():
    from app import obtener_conexion

    return obtener_conexion()


def _render(titulo, contenido):
    from app import render_layout

    return render_layout(titulo, contenido, seccion_activa="cheques")


def contar_alertas_cheques(cursor=None):
    conexion = None
    propio_cursor = cursor is None
    try:
        if cursor is None:
            conexion = _obtener_conexion()
            cursor = conexion.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM cheque
            WHERE estado IN ('EN_CARTERA', 'DEPOSITADO')
              AND fecha_cobro <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        """)
        return int(cursor.fetchone()[0])
    finally:
        if propio_cursor and cursor:
            cursor.close()
        if conexion:
            conexion.close()


def obtener_alertas_cheques(cursor=None):
    conexion = None
    propio_cursor = cursor is None
    try:
        if cursor is None:
            conexion = _obtener_conexion()
            cursor = conexion.cursor()
        cursor.execute("""
            SELECT c.id_cheque,
                   c.numero,
                   c.banco,
                   c.fecha_cobro,
                   c.estado,
                   p.tipo,
                   p.monto,
                   COALESCE(cl.nombre, pr.razon_social) AS contraparte
            FROM cheque AS c
            INNER JOIN pago AS p ON p.id_pago = c.id_pago
            LEFT JOIN cliente AS cl ON cl.id_cliente = p.id_cliente
            LEFT JOIN proveedor AS pr ON pr.id_proveedor = p.id_proveedor
            WHERE c.estado IN ('EN_CARTERA', 'DEPOSITADO')
              AND c.fecha_cobro <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
            ORDER BY c.fecha_cobro, c.numero
        """)
        return cursor.fetchall()
    finally:
        if propio_cursor and cursor:
            cursor.close()
        if conexion:
            conexion.close()


def _datos_formulario(formulario):
    tipo = formulario.get("tipo", "").strip().upper()
    contraparte_id = formulario.get("id_contraparte", "").strip()
    numero = formulario.get("numero", "").strip()
    banco = formulario.get("banco", "").strip()
    monto_texto = formulario.get("monto", "").strip()
    fecha_vencimiento = formulario.get("fecha_cobro", "").strip()

    if tipo not in {"COBRO", "PAGO"}:
        raise ValueError("Selecciona si es un cheque recibido o emitido.")
    if not numero or len(numero) > 20:
        raise ValueError("El número de cheque es obligatorio y no puede superar 20 caracteres.")
    if not banco or len(banco) > 50:
        raise ValueError("El banco es obligatorio y no puede superar 50 caracteres.")

    try:
        contraparte_id = int(contraparte_id)
        monto = Decimal(monto_texto)
        fecha_cobro = datetime.strptime(fecha_vencimiento, "%Y-%m-%d").date()
    except (ValueError, InvalidOperation):
        raise ValueError("Revisa el cliente/proveedor, el monto y la fecha de cobro.")

    if contraparte_id <= 0 or not monto.is_finite() or monto <= 0:
        raise ValueError("La contraparte debe ser válida y el monto debe ser mayor que cero.")

    return tipo, contraparte_id, numero, banco, monto, fecha_cobro


def _cargar_contrapartes():
    conexion = None
    cursor = None
    clientes = []
    proveedores = []
    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT id_cliente, nombre FROM cliente WHERE activo = 1 ORDER BY nombre")
        clientes = cursor.fetchall()
        cursor.execute("SELECT id_proveedor, razon_social FROM proveedor WHERE activo = 1 ORDER BY razon_social")
        proveedores = cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()
    return clientes, proveedores


@cheques_bp.route("/")
def listar():
    solo_lectura = session.get("rol") not in {"ADMIN", "ADMINISTRACION"}
    busqueda = request.args.get("q", "").strip()
    estado = request.args.get("estado", "")
    tipo = request.args.get("tipo", "")
    if estado and estado not in ESTADOS_CHEQUE:
        estado = ""
    if tipo and tipo not in {"COBRO", "PAGO"}:
        tipo = ""

    cheques = []
    alertas = []
    cantidad_alertas = 0
    conexion = None
    cursor = None
    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        condiciones = []
        parametros = []
        if estado:
            condiciones.append("c.estado = %s")
            parametros.append(estado)
        if tipo:
            condiciones.append("p.tipo = %s")
            parametros.append(tipo)
        if busqueda:
            condiciones.append("(c.numero LIKE %s OR c.banco LIKE %s OR cl.nombre LIKE %s OR pr.razon_social LIKE %s)")
            filtro = f"%{busqueda}%"
            parametros.extend((filtro, filtro, filtro, filtro))
        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        cursor.execute(f"""
            SELECT c.id_cheque, c.id_pago, c.numero, c.banco, c.fecha_cobro,
                   c.estado, p.tipo, p.monto,
                   COALESCE(cl.nombre, pr.razon_social) AS contraparte
            FROM cheque AS c
            INNER JOIN pago AS p ON p.id_pago = c.id_pago
            LEFT JOIN cliente AS cl ON cl.id_cliente = p.id_cliente
            LEFT JOIN proveedor AS pr ON pr.id_proveedor = p.id_proveedor
            {where}
            ORDER BY c.fecha_cobro, c.numero
        """, tuple(parametros))
        cheques = cursor.fetchall()
        cantidad_alertas = contar_alertas_cheques(cursor)
        alertas = obtener_alertas_cheques(cursor)
    except Exception as error:
        print(f"Error al cargar cheques: {error}")
        flash("No se pudo cargar el módulo de cheques. Verifica la conexión con la base de datos.", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    filas = ""
    for cheque in cheques:
        id_cheque, id_pago, numero, banco, fecha, estado_actual, tipo_actual, monto, contraparte = cheque
        numero_html = html.escape(str(numero))
        banco_html = html.escape(str(banco))
        fecha_html = fecha.strftime("%d/%m/%Y") if hasattr(fecha, "strftime") else html.escape(str(fecha))
        contraparte_html = html.escape(str(contraparte or "—"))
        monto_html = f"${Decimal(str(monto)):,.2f}"
        tipo_label = "Recibido" if tipo_actual == "COBRO" else "Emitido"
        clase_estado = "success" if estado_actual == "COBRADO" else "danger" if estado_actual == "RECHAZADO" else "warning"
        if solo_lectura:
            acciones_cheque = '<td class="text-muted small">Solo consulta</td>'
        else:
            selector_estados = "".join(
                f'<option value="{estado_opcion}"{" selected" if estado_opcion == estado_actual else ""}>{estado_opcion.replace("_", " ").title()}</option>'
                for estado_opcion in sorted(ESTADOS_CHEQUE)
            )
            acciones_cheque = f"""
            <td>
                <form method="post" action="{url_for('cheques.cambiar_estado', id_cheque=id_cheque)}" class="d-flex gap-1">
                    <select class="form-select form-select-sm" name="estado" aria-label="Estado del cheque {numero_html}">{selector_estados}</select>
                    <button class="btn btn-sm btn-outline-primary" type="submit" title="Actualizar estado"><i class="bi bi-check-lg"></i></button>
                </form>
            </td>
            """
        fecha_alerta = (
            fecha <= date.today() + timedelta(days=7)
            and estado_actual in ESTADOS_PENDIENTES
        )
        clase_fecha = "text-danger fw-bold" if fecha_alerta else ""
        filas += f"""
        <tr>
            <td class="font-monospace fw-semibold">{numero_html}</td>
            <td>{banco_html}</td>
            <td>{tipo_label}</td>
            <td>{contraparte_html}</td>
            <td class="text-end">{monto_html}</td>
            <td class="{clase_fecha}">{fecha_html}</td>
            <td><span class="badge text-bg-{clase_estado}">{estado_actual.replace('_', ' ').title()}</span></td>
            {acciones_cheque}
        </tr>
        """

    if not filas:
        filas = '<tr><td colspan="8" class="py-4 text-center text-muted">No se encontraron cheques.</td></tr>'

    alertas_html = ""
    if alertas:
        alertas_filas = "".join(
            f"<li><strong>{html.escape(str(item[1]))}</strong> · {html.escape(str(item[2]))} · "
            f"{html.escape(str(item[7] or 'Sin contraparte'))} · "
            f"{'venció' if item[3] < date.today() else 'vence'} "
            f"{item[3].strftime('%d/%m/%Y') if hasattr(item[3], 'strftime') else html.escape(str(item[3]))}</li>"
            for item in alertas
        )
        alertas_html = f"""
        <div class="alert alert-warning border-start border-4 border-warning" role="alert">
            <h2 class="h5"><i class="bi bi-exclamation-triangle-fill"></i> Cheques vencidos o próximos a vencer ({cantidad_alertas})</h2>
            <ul class="mb-0">{alertas_filas}</ul>
        </div>
        """

    busqueda_html = html.escape(busqueda, quote=True)
    etiqueta_alertas = "alerta" if cantidad_alertas == 1 else "alertas"
    contenido = f"""
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <h1 class="h3 fw-bold mb-1">Cheques</h1>
            <p class="text-muted mb-0">Control de cheques recibidos y emitidos, vencimientos y estados.</p>
        </div>
        {'' if solo_lectura else f'<a href="{url_for("cheques.nuevo")}" class="btn btn-primary"><i class="bi bi-plus-lg"></i> Registrar cheque</a>'}
    </div>
    {alertas_html}
    <section class="card border-0 shadow-sm">
        <div class="card-header bg-white py-3">
            <form method="get" class="row g-2 align-items-end">
                <div class="col-lg-5">
                    <label class="form-label" for="q">Buscar cheque</label>
                    <input id="q" name="q" type="search" class="form-control" value="{busqueda_html}" placeholder="Número, banco o cliente/proveedor">
                </div>
                <div class="col-sm-5 col-lg-3">
                    <label class="form-label" for="tipo">Operación</label>
                    <select id="tipo" name="tipo" class="form-select">
                        <option value="">Todas</option>
                        <option value="COBRO" {'selected' if tipo == 'COBRO' else ''}>Recibidos</option>
                        <option value="PAGO" {'selected' if tipo == 'PAGO' else ''}>Emitidos</option>
                    </select>
                </div>
                <div class="col-sm-5 col-lg-3">
                    <label class="form-label" for="estado">Estado</label>
                    <select id="estado" name="estado" class="form-select">
                        <option value="">Todos</option>
                        {''.join(f'<option value="{e}"{" selected" if e == estado else ""}>{e.replace("_", " ").title()}</option>' for e in sorted(ESTADOS_CHEQUE))}
                    </select>
                </div>
                <div class="col-sm-2 col-lg-1 d-grid"><button class="btn btn-outline-primary" type="submit" title="Filtrar"><i class="bi bi-search"></i></button></div>
            </form>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead><tr><th>Número</th><th>Banco</th><th>Tipo</th><th>Cliente / proveedor</th><th class="text-end">Monto</th><th>Fecha cobro</th><th>Estado</th><th>{'Acceso' if solo_lectura else 'Actualizar'}</th></tr></thead>
                <tbody>{filas}</tbody>
            </table>
        </div>
        <div class="card-footer bg-white text-muted small">{len(cheques)} cheques · {cantidad_alertas} {etiqueta_alertas} de vencimiento</div>
    </section>
    """
    return _render("Cheques", contenido)


@cheques_bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        conexion = None
        cursor = None
        try:
            tipo, contraparte_id, numero, banco, monto, fecha_cobro = _datos_formulario(request.form)
            conexion = _obtener_conexion()
            cursor = conexion.cursor()

            if tipo == "COBRO":
                cursor.execute("SELECT id_cliente FROM cliente WHERE id_cliente = %s AND activo = 1", (contraparte_id,))
                id_cliente = contraparte_id
                id_proveedor = None
            else:
                cursor.execute("SELECT id_proveedor FROM proveedor WHERE id_proveedor = %s AND activo = 1", (contraparte_id,))
                id_cliente = None
                id_proveedor = contraparte_id
            if not cursor.fetchone():
                raise ValueError("El cliente o proveedor elegido no existe o está inactivo.")

            cursor.execute("""
                INSERT INTO pago (id_cliente, id_proveedor, tipo, fecha_vencimiento, monto, medio)
                VALUES (%s, %s, %s, %s, %s, 'CHEQUE')
            """, (id_cliente, id_proveedor, tipo, fecha_cobro, monto))
            id_pago = cursor.lastrowid
            cursor.execute("""
                INSERT INTO cheque (id_pago, numero, banco, fecha_cobro, estado)
                VALUES (%s, %s, %s, %s, 'EN_CARTERA')
            """, (id_pago, numero, banco, fecha_cobro))
            conexion.commit()
            flash("Cheque registrado correctamente.", "success")
            return redirect(url_for("cheques.listar"))
        except ValueError as error:
            if conexion:
                conexion.rollback()
            flash(str(error), "warning")
        except Exception as error:
            if conexion:
                conexion.rollback()
            print(f"Error al registrar cheque: {error}")
            flash("No se pudo registrar el cheque. Revisa que el número no esté duplicado y que la base esté disponible.", "danger")
        finally:
            if cursor:
                cursor.close()
            if conexion:
                conexion.close()

    try:
        clientes, proveedores = _cargar_contrapartes()
    except Exception as error:
        print(f"Error al cargar clientes y proveedores para cheques: {error}")
        clientes, proveedores = [], []
        flash("No se pudieron cargar clientes y proveedores.", "danger")

    opciones_clientes = "".join(
        f'<option value="{int(row[0])}">{html.escape(str(row[1]))}</option>' for row in clientes
    )
    opciones_proveedores = "".join(
        f'<option value="{int(row[0])}">{html.escape(str(row[1]))}</option>' for row in proveedores
    )
    fecha_hoy = date.today().isoformat()
    contenido = f"""
    <div class="row justify-content-center">
        <div class="col-lg-7 col-xl-6">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h1 class="h3 fw-bold mb-0">Registrar cheque</h1>
                <a href="{url_for('cheques.listar')}" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Volver</a>
            </div>
            <section class="card border-0 shadow-sm"><div class="card-body p-4">
                <form method="post" action="{url_for('cheques.nuevo')}" id="formCheque">
                    <div class="mb-3">
                        <label for="tipo" class="form-label">Tipo de operación</label>
                        <select id="tipo" name="tipo" class="form-select" required>
                            <option value="COBRO">Cheque recibido (cobro)</option>
                            <option value="PAGO">Cheque emitido (pago)</option>
                        </select>
                    </div>
                    <div class="mb-3" id="campoCliente">
                        <label for="cliente" class="form-label">Cliente</label>
                        <select id="cliente" name="id_contraparte" class="form-select" required>
                            <option value="">Selecciona cliente</option>{opciones_clientes}
                        </select>
                    </div>
                    <div class="mb-3 d-none" id="campoProveedor">
                        <label for="proveedor" class="form-label">Proveedor</label>
                        <select id="proveedor" class="form-select" disabled>
                            <option value="">Selecciona proveedor</option>{opciones_proveedores}
                        </select>
                    </div>
                    <div class="row g-3">
                        <div class="col-md-6">
                            <label for="numero" class="form-label">Número de cheque</label>
                            <input id="numero" name="numero" class="form-control" maxlength="20" required>
                        </div>
                        <div class="col-md-6">
                            <label for="banco" class="form-label">Banco</label>
                            <input id="banco" name="banco" class="form-control" maxlength="50" required>
                        </div>
                        <div class="col-md-6">
                            <label for="monto" class="form-label">Monto</label>
                            <input id="monto" name="monto" type="number" min="0.01" step="0.01" class="form-control" required>
                        </div>
                        <div class="col-md-6">
                            <label for="fecha_cobro" class="form-label">Fecha de cobro / vencimiento</label>
                            <input id="fecha_cobro" name="fecha_cobro" type="date" class="form-control" value="{fecha_hoy}" required>
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary mt-4"><i class="bi bi-check-lg"></i> Registrar cheque</button>
                </form>
            </div></section>
        </div>
    </div>
    <script>
        const tipoCheque = document.getElementById('tipo');
        const clienteSelect = document.getElementById('cliente');
        const proveedorSelect = document.getElementById('proveedor');
        const campoCliente = document.getElementById('campoCliente');
        const campoProveedor = document.getElementById('campoProveedor');
        function actualizarContraparte() {{
            const cobro = tipoCheque.value === 'COBRO';
            campoCliente.classList.toggle('d-none', !cobro);
            campoProveedor.classList.toggle('d-none', cobro);
            clienteSelect.disabled = !cobro;
            clienteSelect.required = cobro;
            proveedorSelect.disabled = cobro;
            proveedorSelect.required = !cobro;
            proveedorSelect.name = cobro ? '' : 'id_contraparte';
            clienteSelect.name = cobro ? 'id_contraparte' : '';
        }}
        tipoCheque.addEventListener('change', actualizarContraparte);
        actualizarContraparte();
    </script>
    """
    return _render("Registrar cheque", contenido)


@cheques_bp.route("/<int:id_cheque>/estado", methods=["POST"])
def cambiar_estado(id_cheque):
    estado = request.form.get("estado", "").strip().upper()
    if estado not in ESTADOS_CHEQUE:
        flash("El estado seleccionado no es válido.", "warning")
        return redirect(url_for("cheques.listar"))

    conexion = None
    cursor = None
    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("UPDATE cheque SET estado = %s WHERE id_cheque = %s", (estado, id_cheque))
        conexion.commit()
        if cursor.rowcount:
            flash("Estado del cheque actualizado.", "success")
        else:
            flash("No se encontró el cheque.", "warning")
    except Exception as error:
        if conexion:
            conexion.rollback()
        print(f"Error al actualizar estado del cheque {id_cheque}: {error}")
        flash("No se pudo actualizar el estado del cheque.", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()
    return redirect(url_for("cheques.listar"))
