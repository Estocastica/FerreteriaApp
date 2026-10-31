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

MAPA_ROLES = {
    "ADMIN": "ADMIN",
    "ADMINISTRADOR": "ADMIN",
    "PROPIETARIO": "ADMIN",
    "DUENO": "ADMIN",
    "DUEÑO": "ADMIN",
    "ADMINISTRACION": "ADMINISTRACION",
    "ADMINISTRATIVO": "ADMINISTRACION",
    "ADMINISTRATIVA": "ADMINISTRACION",
    "DEPOSITO": "DEPOSITO",
    "DEPÓSITO": "DEPOSITO",
    "ALMACEN": "DEPOSITO",
    "VENDEDOR": "VENDEDOR",
    "VENDEDORA": "VENDEDOR",
    "VENTAS": "VENDEDOR",
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


def verificar_password(password, hash_guardado):
    if not hash_guardado:
        return False

    hash_guardado = str(hash_guardado).strip()
    password = str(password)

    # 1. Verificación directa contra texto plano (común en cargas y maquetas iniciales)
    if hmac.compare_digest(hash_guardado, password):
        return True

    # 2. Verificación SHA-256 (64 caracteres hexadecimales)
    if re.fullmatch(r"[0-9a-fA-F]{64}", hash_guardado):
        hash_sha256 = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if hmac.compare_digest(hash_sha256.lower(), hash_guardado.lower()):
            return True

    # 3. Verificación MD5 (32 caracteres hexadecimales)
    if re.fullmatch(r"[0-9a-fA-F]{32}", hash_guardado):
        hash_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
        if hmac.compare_digest(hash_md5.lower(), hash_guardado.lower()):
            return True

    # 4. Verificación SHA-1 (40 caracteres hexadecimales)
    if re.fullmatch(r"[0-9a-fA-F]{40}", hash_guardado):
        hash_sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest()
        if hmac.compare_digest(hash_sha1.lower(), hash_guardado.lower()):
            return True

    # 5. Formatos estándar de Werkzeug / PBKDF2 / Scrypt
    try:
        if check_password_hash(hash_guardado, password):
            return True
    except (TypeError, ValueError):
        pass

    return False


def normalizar_rol(rol_raw):
    if not rol_raw:
        return None
    rol_limpio = str(rol_raw).strip().upper()
    return MAPA_ROLES.get(rol_limpio, rol_limpio)


def autenticar(username, password):
    from app import obtener_conexion

    usuario_input = str(username or "").strip()
    if not usuario_input:
        return None

    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        # LEFT JOIN previene exclusión si id_empleado es NULL o no existe registro en empleado
        cursor.execute(
            """SELECT u.id_usuario,
                      u.id_empleado,
                      u.username,
                      u.password_hash,
                      u.rol,
                      COALESCE(e.nombre, u.username) AS nombre
               FROM usuario AS u
               LEFT JOIN empleado AS e ON e.id_empleado = u.id_empleado
               WHERE LOWER(TRIM(u.username)) = LOWER(%s)
                 AND (u.activo = 1 OR u.activo IS NULL)
               LIMIT 1""",
            (usuario_input,)
        )
        usuario = cursor.fetchone()
        if not usuario:
            return None

        id_usuario = int(usuario[0])
        id_empleado = int(usuario[1]) if usuario[1] is not None else id_usuario
        nombre_usuario = str(usuario[2])
        hash_guardado = usuario[3]
        rol_canonico = normalizar_rol(usuario[4])
        nombre_persona = str(usuario[5] or nombre_usuario)

        if rol_canonico not in PERFILES:
            return None

        if not verificar_password(password, hash_guardado):
            return None

        return {
            "id_usuario": id_usuario,
            "id_empleado": id_empleado,
            "username": nombre_usuario,
            "rol": rol_canonico,
            "nombre": nombre_persona,
        }
    except Exception as error:
        print(f"Error durante el proceso de autenticación: {error}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conexion:
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