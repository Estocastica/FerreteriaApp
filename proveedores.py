import html

from flask import Blueprint, flash, redirect, request, url_for, session


proveedores_bp = Blueprint("proveedores", __name__, url_prefix="/proveedores")


def _obtener_conexion():
    from app import obtener_conexion

    return obtener_conexion()


def _render(titulo, contenido):
    from app import render_layout

    return render_layout(titulo, contenido, seccion_activa="proveedores")


def _validar_formulario(formulario):
    razon_social = formulario.get("razon_social", "").strip()
    telefono = formulario.get("telefono", "").strip()
    email = formulario.get("email", "").strip()

    if not razon_social:
        raise ValueError("La razón social es obligatoria.")
    if len(razon_social) > 100:
        raise ValueError("La razón social no puede superar los 100 caracteres.")
    if len(telefono) > 30:
        raise ValueError("El teléfono no puede superar los 30 caracteres.")
    if len(email) > 100:
        raise ValueError("El email no puede superar los 100 caracteres.")
    if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
        raise ValueError("Ingresa un email válido.")

    return razon_social, telefono or None, email or None


def _formulario_proveedor(accion, proveedor=None):
    proveedor = proveedor or ("", "", "", "")
    proveedor_id = proveedor[0]
    razon_social = html.escape(str(proveedor[1]), quote=True)
    telefono = html.escape(str(proveedor[2] or ""), quote=True)
    email = html.escape(str(proveedor[3] or ""), quote=True)
    titulo = "Editar proveedor" if proveedor_id else "Nuevo proveedor"
    texto_boton = "Guardar cambios" if proveedor_id else "Registrar proveedor"

    contenido = f"""
    <div class="row justify-content-center">
        <div class="col-lg-7 col-xl-6">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h1 class="h3 fw-bold mb-0">{titulo}</h1>
                <a href="{url_for('proveedores.listar')}" class="btn btn-outline-secondary">
                    <i class="bi bi-arrow-left"></i> Volver
                </a>
            </div>
            <section class="card border-0 shadow-sm">
                <div class="card-body p-4">
                    <form method="post" action="{accion}">
                        <div class="mb-3">
                            <label for="razon_social" class="form-label">Razón social</label>
                            <input id="razon_social" name="razon_social" class="form-control" maxlength="100" value="{razon_social}" required autofocus>
                        </div>
                        <div class="mb-3">
                            <label for="telefono" class="form-label">Teléfono</label>
                            <input id="telefono" name="telefono" type="tel" class="form-control" maxlength="30" value="{telefono}">
                        </div>
                        <div class="mb-4">
                            <label for="email" class="form-label">Email</label>
                            <input id="email" name="email" type="email" class="form-control" maxlength="100" value="{email}">
                        </div>
                        <button type="submit" class="btn btn-primary">
                            <i class="bi bi-check-lg"></i> {texto_boton}
                        </button>
                    </form>
                </div>
            </section>
        </div>
    </div>
    """
    return _render(titulo, contenido)


@proveedores_bp.route("/")
def listar():
    solo_lectura = session.get("rol") not in {"ADMIN", "ADMINISTRACION"}
    busqueda = request.args.get("q", "").strip()
    estado = request.args.get("estado", "activos")
    if estado not in {"activos", "inactivos", "todos"}:
        estado = "activos"

    proveedores = []
    conexion = None
    cursor = None
    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()

        condiciones = []
        parametros = []
        if estado == "activos":
            condiciones.append("activo = 1")
        elif estado == "inactivos":
            condiciones.append("activo = 0")
        if busqueda:
            condiciones.append("(razon_social LIKE %s OR telefono LIKE %s OR email LIKE %s)")
            filtro = f"%{busqueda}%"
            parametros.extend((filtro, filtro, filtro))

        where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        cursor.execute(
            f"""SELECT id_proveedor, razon_social, telefono, email, activo
                FROM proveedor
                {where}
                ORDER BY razon_social""",
            tuple(parametros)
        )
        proveedores = cursor.fetchall()
    except Exception as error:
        print(f"Error al consultar proveedores: {error}")
        flash("No se pudieron cargar los proveedores. Comprueba la conexión con MySQL.", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    filas = ""
    for proveedor in proveedores:
        proveedor_id = int(proveedor[0])
        razon_social = html.escape(str(proveedor[1]))
        telefono = html.escape(str(proveedor[2] or "—"))
        email = html.escape(str(proveedor[3] or "—"))
        activo = bool(proveedor[4])
        estado_html = (
            '<span class="badge text-bg-success">Activo</span>'
            if activo else '<span class="badge text-bg-secondary">Inactivo</span>'
        )
        accion_estado = "Desactivar" if activo else "Reactivar"
        clase_estado = "outline-danger" if activo else "outline-success"
        icono_estado = "bi-person-dash" if activo else "bi-person-check"

        if solo_lectura:
            acciones_html = '<td class="text-end text-muted">Solo consulta</td>'
        else:
            acciones_html = f"""
            <td class="text-end text-nowrap">
                <a class="btn btn-sm btn-outline-primary" href="{url_for('proveedores.editar', id_proveedor=proveedor_id)}" title="Editar proveedor">
                    <i class="bi bi-pencil"></i><span class="visually-hidden">Editar</span>
                </a>
                <form class="d-inline" method="post" action="{url_for('proveedores.cambiar_estado', id_proveedor=proveedor_id)}">
                    <button class="btn btn-sm btn-{clase_estado}" type="submit" title="{accion_estado} proveedor">
                        <i class="bi {icono_estado}"></i><span class="visually-hidden">{accion_estado}</span>
                    </button>
                </form>
            </td>
            """

        filas += f"""
        <tr>
            <td class="fw-semibold">{razon_social}</td>
            <td>{telefono}</td>
            <td>{email}</td>
            <td>{estado_html}</td>
            {acciones_html}
        </tr>
        """

    if not filas:
        filas = '<tr><td colspan="5" class="py-4 text-center text-muted">No se encontraron proveedores.</td></tr>'

    busqueda_html = html.escape(busqueda, quote=True)
    activos = sum(1 for proveedor in proveedores if proveedor[4])
    contenido = f"""
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <h1 class="h3 fw-bold mb-1">Proveedores</h1>
            <p class="text-muted mb-0">Directorio de proveedores y datos de contacto.</p>
        </div>
        {'' if solo_lectura else f'<a href="{url_for("proveedores.nuevo")}" class="btn btn-primary"><i class="bi bi-plus-lg"></i> Nuevo proveedor</a>'}
    </div>

    <section class="card border-0 shadow-sm">
        <div class="card-header bg-white py-3">
            <form method="get" class="row g-2 align-items-end">
                <div class="col-md-7">
                    <label class="form-label" for="q">Buscar proveedor</label>
                    <input id="q" name="q" type="search" class="form-control" value="{busqueda_html}" placeholder="Razón social, teléfono o email">
                </div>
                <div class="col-md-3">
                    <label class="form-label" for="estado">Estado</label>
                    <select id="estado" name="estado" class="form-select">
                        <option value="activos" {'selected' if estado == 'activos' else ''}>Activos</option>
                        <option value="inactivos" {'selected' if estado == 'inactivos' else ''}>Inactivos</option>
                        <option value="todos" {'selected' if estado == 'todos' else ''}>Todos</option>
                    </select>
                </div>
                <div class="col-md-2 d-grid">
                    <button class="btn btn-outline-primary" type="submit"><i class="bi bi-search"></i> Buscar</button>
                </div>
            </form>
        </div>
        <div class="table-responsive">
            <table class="table table-hover align-middle mb-0">
                <thead>
                    <tr><th>Razón social</th><th>Teléfono</th><th>Email</th><th>Estado</th><th class="text-end">Acciones</th></tr>
                </thead>
                <tbody>{filas}</tbody>
            </table>
        </div>
        <div class="card-footer bg-white text-muted small">
            {len(proveedores)} registros mostrados · {activos} activos en esta vista
        </div>
    </section>
    """
    return _render("Proveedores", contenido)


@proveedores_bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if request.method == "POST":
        try:
            razon_social, telefono, email = _validar_formulario(request.form)
            conexion = _obtener_conexion()
            cursor = conexion.cursor()
            try:
                cursor.execute(
                    """INSERT INTO proveedor (razon_social, telefono, email, activo)
                       VALUES (%s, %s, %s, 1)""",
                    (razon_social, telefono, email)
                )
                conexion.commit()
            except Exception:
                conexion.rollback()
                raise
            finally:
                cursor.close()
                conexion.close()
            flash("Proveedor registrado correctamente.", "success")
            return redirect(url_for("proveedores.listar"))
        except ValueError as error:
            flash(str(error), "warning")
        except Exception as error:
            print(f"Error al registrar proveedor: {error}")
            flash("No se pudo registrar el proveedor. Comprueba los datos y la conexión.", "danger")

    return _formulario_proveedor(url_for("proveedores.nuevo"))


@proveedores_bp.route("/<int:id_proveedor>/editar", methods=["GET", "POST"])
def editar(id_proveedor):
    proveedor = None
    conexion = None
    cursor = None
    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        if request.method == "POST":
            razon_social, telefono, email = _validar_formulario(request.form)
            cursor.execute(
                """UPDATE proveedor
                   SET razon_social = %s, telefono = %s, email = %s
                   WHERE id_proveedor = %s""",
                (razon_social, telefono, email, id_proveedor)
            )
            conexion.commit()
            if cursor.rowcount:
                flash("Proveedor actualizado correctamente.", "success")
            else:
                flash("No se encontraron cambios para guardar.", "info")
            return redirect(url_for("proveedores.listar"))

        cursor.execute(
            """SELECT id_proveedor, razon_social, telefono, email
               FROM proveedor WHERE id_proveedor = %s""",
            (id_proveedor,)
        )
        proveedor = cursor.fetchone()
    except ValueError as error:
        if conexion:
            conexion.rollback()
        flash(str(error), "warning")
    except Exception as error:
        if conexion:
            conexion.rollback()
        print(f"Error al editar proveedor {id_proveedor}: {error}")
        flash("No se pudo cargar o actualizar el proveedor.", "danger")
        return redirect(url_for("proveedores.listar"))
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    if not proveedor:
        flash("El proveedor solicitado no existe.", "warning")
        return redirect(url_for("proveedores.listar"))

    accion = url_for("proveedores.editar", id_proveedor=id_proveedor)
    return _formulario_proveedor(accion, proveedor)


@proveedores_bp.route("/<int:id_proveedor>/estado", methods=["POST"])
def cambiar_estado(id_proveedor):
    conexion = None
    cursor = None
    try:
        conexion = _obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """UPDATE proveedor
               SET activo = CASE WHEN activo = 1 THEN 0 ELSE 1 END
               WHERE id_proveedor = %s""",
            (id_proveedor,)
        )
        conexion.commit()
        if cursor.rowcount:
            flash("Estado del proveedor actualizado.", "success")
        else:
            flash("No se encontró el proveedor.", "warning")
    except Exception as error:
        if conexion:
            conexion.rollback()
        print(f"Error al cambiar estado del proveedor {id_proveedor}: {error}")
        flash("No se pudo cambiar el estado del proveedor.", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    return redirect(url_for("proveedores.listar"))
