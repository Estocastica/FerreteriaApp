import hashlib
import hmac
import re

from flask import redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


PERFILES = {
    "ADMIN": {"nombre": "Propietario", "inicio": "inicio"},
    "ADMINISTRACION": {"nombre": "Administración", "inicio": "inicio"},
    "DEPOSITO": {"nombre": "Depósito", "inicio": "productos"},
    "VENDEDOR": {"nombre": "Vendedor", "inicio": "ventas.nueva_venta"},
}

PERMISOS = {
    "DEPOSITO": {
        ("productos", "GET"),
        ("productos_nuevo", "GET"),
        ("productos_nuevo", "POST"),
    },
    "VENDEDOR": {
        ("productos", "GET"),
        ("ventas.listar_ventas", "GET"),
        ("ventas.nueva_venta", "GET"),
        ("ventas.nueva_venta", "POST"),
        ("ventas.comprobante", "GET"),
    },
}

VISTAS_ADMINISTRACION_BLOQUEADAS = {
    "productos_nuevo",
    "ventas.nueva_venta",
}


def autenticar(username, password):
    from app import obtener_conexion

    conexion = obtener_conexion()
    cursor = None
    try:
        cursor = conexion.cursor()
        cursor.execute(
            """SELECT u.id_usuario, u.id_empleado, u.username, u.password_hash,
                      u.rol, e.nombre
               FROM usuario AS u
               INNER JOIN empleado AS e ON e.id_empleado = u.id_empleado
               WHERE u.username = %s AND u.activo = 1""",
            (username.strip(),)
        )
        usuario = cursor.fetchone()
        if not usuario:
            return None

        hash_guardado = str(usuario[3])
        if re.fullmatch(r"[0-9a-fA-F]{64}", hash_guardado):
            hash_ingresado = hashlib.sha256(password.encode("utf-8")).hexdigest()
            valido = hmac.compare_digest(hash_ingresado.lower(), hash_guardado.lower())
            if valido:
                cursor.execute(
                    "UPDATE usuario SET password_hash = %s WHERE id_usuario = %s",
                    (generate_password_hash(password), usuario[0])
                )
                conexion.commit()
        else:
            try:
                valido = check_password_hash(hash_guardado, password)
            except (TypeError, ValueError):
                valido = False

        if not valido or usuario[4] not in PERFILES:
            return None

        return {
            "id_usuario": int(usuario[0]),
            "id_empleado": int(usuario[1]),
            "username": str(usuario[2]),
            "rol": str(usuario[4]),
            "nombre": str(usuario[5]),
        }
    finally:
        if cursor:
            cursor.close()
        conexion.close()


def perfil_actual():
    rol = session.get("rol")
    return PERFILES.get(rol, {})


def rol_actual():
    return session.get("rol")


def inicio_actual():
    perfil = perfil_actual()
    return perfil.get("inicio", "login")


def puede_acceder(endpoint, method):
    rol = rol_actual()
    if rol == "ADMIN":
        return True
    method = "GET" if method == "HEAD" else method
    if rol == "ADMINISTRACION":
        return endpoint not in VISTAS_ADMINISTRACION_BLOQUEADAS
    if rol not in PERMISOS:
        return False
    return (endpoint, method) in PERMISOS[rol]


def registrar_control_acceso(app):
    @app.before_request
    def controlar_acceso():
        if request.endpoint in {"login", "logout", "static"}:
            return None

        if not session.get("id_usuario") or not rol_actual() in PERFILES:
            return redirect(url_for("login"))

        if request.endpoint == "inicio" and rol_actual() in {"DEPOSITO", "VENDEDOR"}:
            return redirect(url_for(inicio_actual()))

        if not puede_acceder(request.endpoint, request.method):
            return redirect(url_for(inicio_actual()))

        return None
