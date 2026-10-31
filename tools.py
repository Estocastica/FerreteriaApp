import os
import subprocess
import shutil
from pathlib import Path


RAIZ_PROYECTO = Path.cwd().resolve()


def _resolver_ruta(ruta):

    ruta_resuelta = Path(ruta).resolve()

    try:
        ruta_resuelta.relative_to(RAIZ_PROYECTO)
    except ValueError as error:
        raise ValueError(
            "La ruta debe estar dentro de la carpeta del proyecto."
        ) from error

    return ruta_resuelta


# ==========================================
# LEER ARCHIVO
# ==========================================

def leer_archivo(ruta):

    with open(
        _resolver_ruta(ruta),
        "r",
        encoding="utf-8"
    ) as f:

        return f.read()


# ==========================================
# CREAR ARCHIVO
# ==========================================

def crear_archivo(ruta, contenido):

    ruta = _resolver_ruta(ruta)
    carpeta = ruta.parent

    carpeta.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        ruta,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(contenido)

    return (
        f"Archivo creado: {ruta}"
    )


# ==========================================
# MODIFICAR ARCHIVO
# ==========================================

def escribir_archivo(ruta, contenido):

    ruta = _resolver_ruta(ruta)
    carpeta = ruta.parent 

    carpeta.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        ruta,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(contenido)

    return (
        f"Archivo actualizado: {ruta}"
    )


# ==========================================
# VERIFICAR EXISTENCIA
# ==========================================

def existe_archivo(ruta):

    return _resolver_ruta(ruta).exists()


def crear_carpeta(ruta):

    carpeta = _resolver_ruta(ruta)
    carpeta.mkdir(
        parents=True,
        exist_ok=True
    )

    return f"Carpeta creada: {ruta}"


def mover_ruta(origen, destino):

    ruta_origen = _resolver_ruta(origen)
    ruta_destino = _resolver_ruta(destino)

    if not ruta_origen.exists():
        raise FileNotFoundError(f"No existe: {origen}")

    if ruta_origen == RAIZ_PROYECTO:
        raise ValueError("No se puede mover la carpeta raíz del proyecto.")

    if ruta_destino.exists():
        raise FileExistsError(f"Ya existe: {destino}")

    ruta_destino.parent.mkdir(
        parents=True,
        exist_ok=True
    )
    shutil.move(str(ruta_origen), str(ruta_destino))

    return f"Movido: {origen} -> {destino}"


def eliminar_ruta(ruta):

    ruta_resuelta = _resolver_ruta(ruta)

    if ruta_resuelta == RAIZ_PROYECTO:
        raise ValueError("No se puede eliminar la carpeta raíz del proyecto.")

    if ruta_resuelta.is_dir():
        shutil.rmtree(ruta_resuelta)
    elif ruta_resuelta.exists():
        ruta_resuelta.unlink()
    else:
        raise FileNotFoundError(f"No existe: {ruta}")

    return f"Eliminado: {ruta}"


# ==========================================
# ELIMINAR ARCHIVO
# ==========================================

def eliminar_archivo(ruta):

    if os.path.exists(ruta):

        os.remove(ruta)

        return (
            f"Archivo eliminado: {ruta}"
        )

    return (
        f"No existe: {ruta}"
    )


# ==========================================
# LISTAR ARCHIVOS
# ==========================================

def listar_archivos():

    resultado = []

    for raiz, dirs, archivos in os.walk("."):

        dirs[:] = [

            d for d in dirs

            if d not in [
                "venv",
                "__pycache__",
                ".git",
                "backups"
            ]
        ]

        for archivo in archivos:

            resultado.append(
                os.path.join(
                    raiz,
                    archivo
                )
            )

    return "\n".join(
        sorted(resultado)
    )


# ==========================================
# EJECUTAR PYTHON
# ==========================================

def ejecutar_python(archivo):

    try:

        proceso = subprocess.run(
            ["py", archivo],
            capture_output=True,
            text=True
        )

        return {

            "codigo":
                proceso.returncode,

            "stdout":
                proceso.stdout,

            "stderr":
                proceso.stderr
        }

    except Exception as e:

        return {

            "codigo": -1,

            "stdout": "",

            "stderr": str(e)
        }


# ==========================================
# GUARDAR INFORME
# ==========================================

def guardar_informe(
    nombre,
    contenido
):

    os.makedirs(
        "informes",
        exist_ok=True
    )

    ruta = os.path.join(
        "informes",
        nombre
    )

    with open(
        ruta,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(contenido)

    return ruta


# ==========================================
# LEER CONTEXTO
# ==========================================

def leer_contexto():

    if os.path.exists(
        "contexto.txt"
    ):

        return leer_archivo(
            "contexto.txt"
        )

    return (
        "No existe contexto.txt"
    )


# ==========================================
# COPIA DE SEGURIDAD
# ==========================================

def crear_backup(ruta):

    if not os.path.exists(ruta):

        return None

    os.makedirs(
        "backups",
        exist_ok=True
    )

    nombre = os.path.basename(
        ruta
    )

    backup = os.path.join(
        "backups",
        nombre + ".bak"
    )

    with open(
        ruta,
        "r",
        encoding="utf-8"
    ) as origen:

        contenido = origen.read()

    with open(
        backup,
        "w",
        encoding="utf-8"
    ) as destino:

        destino.write(
            contenido
        )

    return backup