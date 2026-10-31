import csv
import io
from datetime import date

from flask import Blueprint, Response, flash


analisis_bp = Blueprint("analisis", __name__, url_prefix="/analisis")


def _obtener_conexion():
    from app import obtener_conexion

    return obtener_conexion()


def _valor_csv(valor):
    if isinstance(valor, str) and valor.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + valor
    return valor


def _exportar_csv(nombre_archivo, encabezados, consulta):
    conexion = None
    cursor = None
    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(consulta)
        filas = cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    buffer = io.StringIO(newline="")
    escritor = csv.writer(buffer, lineterminator="\r\n")
    escritor.writerow(encabezados)
    escritor.writerows(tuple(_valor_csv(valor) for valor in fila) for fila in filas)
    contenido = ("\ufeff" + buffer.getvalue()).encode("utf-8")

    respuesta = Response(contenido, content_type="text/csv; charset=utf-8")
    respuesta.headers["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@analisis_bp.route("/")
def inicio():
    contenido = """
    <div class="mb-4">
        <h1 class="h3 fw-bold mb-1">Análisis de datos</h1>
        <p class="text-muted mb-0">Descarga los datos operativos para analizarlos en una hoja de cálculo.</p>
    </div>
    <section class="card border-0 shadow-sm">
        <div class="list-group list-group-flush">
            <div class="list-group-item d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2 py-3">
                <div><h2 class="h6 fw-bold mb-1">Ventas</h2><p class="small text-muted mb-0">Comprobantes y detalle de productos, clientes, vendedores y totales.</p></div>
                <a class="btn btn-outline-primary" href="/analisis/ventas.csv"><i class="bi bi-download"></i> Descargar CSV</a>
            </div>
            <div class="list-group-item d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2 py-3">
                <div><h2 class="h6 fw-bold mb-1">Cuentas corrientes</h2><p class="small text-muted mb-0">Límites, cargos, cobros, saldo y porcentaje de uso por cliente.</p></div>
                <a class="btn btn-outline-primary" href="/analisis/cuenta-corriente.csv"><i class="bi bi-download"></i> Descargar CSV</a>
            </div>
            <div class="list-group-item d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2 py-3">
                <div><h2 class="h6 fw-bold mb-1">Cheques</h2><p class="small text-muted mb-0">Número, banco, vencimiento, estado, contraparte y monto.</p></div>
                <a class="btn btn-outline-primary" href="/analisis/cheques.csv"><i class="bi bi-download"></i> Descargar CSV</a>
            </div>
            <div class="list-group-item d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-2 py-3">
                <div><h2 class="h6 fw-bold mb-1">Stock</h2><p class="small text-muted mb-0">Código, producto, categoría, existencias, mínimo y precio.</p></div>
                <a class="btn btn-outline-primary" href="/analisis/stock.csv"><i class="bi bi-download"></i> Descargar CSV</a>
            </div>
        </div>
    </section>
    """
    from app import render_layout

    return render_layout("Análisis de datos", contenido, seccion_activa="analisis")


@analisis_bp.route("/ventas.csv")
def exportar_ventas():
    try:
        return _exportar_csv(
            f"ventas_{date.today():%Y%m%d}.csv",
            [
                "id_venta", "fecha", "estado", "condicion_pago", "cliente", "empleado",
                "codigo_producto", "producto", "cantidad", "precio_unitario", "subtotal_linea", "total_venta",
            ],
            """SELECT v.id_venta,
                      v.fecha,
                      v.estado,
                      v.condicion_pago,
                      c.nombre,
                      e.nombre,
                      p.codigo,
                      p.nombre,
                      COALESCE(d.cantidad, 0),
                      COALESCE(d.precio_unitario, 0),
                      COALESCE(d.cantidad * d.precio_unitario, 0),
                      v.total
               FROM venta AS v
               INNER JOIN cliente AS c ON c.id_cliente = v.id_cliente
               INNER JOIN empleado AS e ON e.id_empleado = v.id_empleado
               LEFT JOIN detalle_venta AS d ON d.id_venta = v.id_venta
               LEFT JOIN producto AS p ON p.id_producto = d.id_producto
               ORDER BY v.fecha DESC, v.id_venta DESC, p.nombre""",
        )
    except Exception as error:
        print(f"Error exportando ventas: {error}")
        flash("No se pudieron exportar las ventas.", "danger")
        from app import render_layout

        return render_layout("Error de exportación", "<p>No se pudo generar el CSV de ventas.</p>", "analisis"), 500


@analisis_bp.route("/cuenta-corriente.csv")
def exportar_cuenta_corriente():
    try:
        return _exportar_csv(
            f"cuenta_corriente_{date.today():%Y%m%d}.csv",
            [
                "id_cliente", "cliente", "tipo_cliente", "limite_credito", "total_cargos",
                "total_cobrado", "saldo_pendiente", "porcentaje_limite",
            ],
            """SELECT id_cliente,
                      nombre,
                      tipo,
                      limite_credito,
                      total_a_cuenta_corriente,
                      total_cobrado,
                      GREATEST(total_a_cuenta_corriente - total_cobrado, 0),
                      ROUND(
                          100 * GREATEST(total_a_cuenta_corriente - total_cobrado, 0)
                          / NULLIF(limite_credito, 0),
                          1
                      )
               FROM v_cuenta_corriente_clientes
               ORDER BY nombre""",
        )
    except Exception as error:
        print(f"Error exportando cuentas corrientes: {error}")
        flash("No se pudo exportar la cuenta corriente.", "danger")
        from app import render_layout

        return render_layout("Error de exportación", "<p>No se pudo generar el CSV de cuenta corriente.</p>", "analisis"), 500


@analisis_bp.route("/cheques.csv")
def exportar_cheques():
    try:
        return _exportar_csv(
            f"cheques_{date.today():%Y%m%d}.csv",
            [
                "id_cheque", "id_pago", "numero", "banco", "fecha_cobro", "estado",
                "tipo_pago", "medio_pago", "fecha_pago", "monto", "cliente", "proveedor",
            ],
            """SELECT ch.id_cheque,
                      ch.id_pago,
                      ch.numero,
                      ch.banco,
                      ch.fecha_cobro,
                      ch.estado,
                      pa.tipo,
                      pa.medio,
                      pa.fecha,
                      pa.monto,
                      cl.nombre,
                      pr.razon_social
               FROM cheque AS ch
               INNER JOIN pago AS pa ON pa.id_pago = ch.id_pago
               LEFT JOIN cliente AS cl ON cl.id_cliente = pa.id_cliente
               LEFT JOIN proveedor AS pr ON pr.id_proveedor = pa.id_proveedor
               ORDER BY ch.fecha_cobro, ch.numero""",
        )
    except Exception as error:
        print(f"Error exportando cheques: {error}")
        flash("No se pudieron exportar los cheques.", "danger")
        from app import render_layout

        return render_layout("Error de exportación", "<p>No se pudo generar el CSV de cheques.</p>", "analisis"), 500


@analisis_bp.route("/stock.csv")
def exportar_stock():
    try:
        return _exportar_csv(
            f"stock_{date.today():%Y%m%d}.csv",
            ["id_producto", "codigo", "producto", "categoria", "stock_actual", "stock_minimo", "precio_venta", "activo"],
            """SELECT p.id_producto,
                      p.codigo,
                      p.nombre,
                      c.nombre,
                      p.stock_actual,
                      p.stock_minimo,
                      p.precio_venta,
                      p.activo
               FROM producto AS p
               LEFT JOIN categoria AS c ON c.id_categoria = p.id_categoria
               ORDER BY p.nombre""",
        )
    except Exception as error:
        print(f"Error exportando stock: {error}")
        flash("No se pudo exportar el stock.", "danger")
        from app import render_layout

        return render_layout("Error de exportación", "<p>No se pudo generar el CSV de stock.</p>", "analisis"), 500
