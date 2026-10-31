from google import genai

from tools import (
    leer_archivo,
    listar_archivos,
    crear_archivo,
    escribir_archivo,
    ejecutar_python,
    existe_archivo,
    crear_carpeta,
    mover_ruta,
    eliminar_ruta
)

import os
from datetime import datetime


# ==========================================
# CONFIGURACION
# ==========================================

cliente = genai.Client()

os.makedirs(
    "informes",
    exist_ok=True
)

os.makedirs(
    "backups",
    exist_ok=True
)

print("\n====================================")
print("AGENTE DESARROLLADOR FERRETERIA")
print("====================================")

print("\nArchivos encontrados:\n")
print(listar_archivos())

print("\nComandos sugeridos:")
print("- Analiza el proyecto")
print("- Corrige errores")
print("- Crea modulo proveedores")
print("- Refactoriza app.py")
print("- Genera CRUD productos")
print("\nEscriba 'salir' para terminar.")


# ==========================================
# FUNCION: CARGAR PROYECTO
# ==========================================

def cargar_codigo_proyecto():

    contexto = ""
    extensiones = (
        ".py",
        ".html",
        ".css",
        ".js",
        ".sql"
    )
    carpetas_ignoradas = {
        "venv",
        ".venv",
        "__pycache__",
        ".git",
        "backups",
        "informes"
    }

    for raiz, carpetas, nombres in os.walk("."):

        carpetas[:] = [
            carpeta for carpeta in carpetas
            if carpeta not in carpetas_ignoradas
        ]

        for nombre in sorted(nombres):

            if not nombre.lower().endswith(extensiones):
                continue

            archivo = os.path.join(raiz, nombre)

            try:
                contenido = leer_archivo(archivo)
                contexto += f"""
====================================================
ARCHIVO: {archivo}
====================================================

{contenido}

"""
            except Exception as e:
                contexto += f"""

ERROR LEYENDO {archivo}

{str(e)}

"""

    return contexto


# ==========================================
# BUCLE PRINCIPAL
# ==========================================

while True:

    pedido = input("\nEva > ")

    if pedido.lower() == "salir":

        print("\nFin de la sesión.")
        break


    # ======================================
    # RECARGA DEL PROYECTO
    # ======================================

    archivos = listar_archivos()

    codigo_proyecto = (
        cargar_codigo_proyecto()
    )


    # ======================================
    # PROMPT
    # ======================================

    prompt = f"""
Eres un desarrollador senior especializado en:

- Python
- Flask
- MySQL
- Bootstrap

Tienes permiso para:

- Crear archivos
- Modificar archivos
- Refactorizar código
- Corregir errores
- Crear módulos completos

Proyecto actual:

{archivos}

Código del proyecto:

{codigo_proyecto}

Pedido del usuario:

{pedido}

IMPORTANTE:

Responde únicamente usando UNO de los siguientes formatos.

PARA CREAR:

CREAR_ARCHIVO: ruta

contenido completo


PARA MODIFICAR:

MODIFICAR_ARCHIVO: ruta

contenido completo


PARA CREAR UNA CARPETA:

CREAR_CARPETA: ruta


PARA MOVER O RENOMBRAR UN ARCHIVO O CARPETA:

MOVER_RUTA: origen -> destino


PARA ELIMINAR UN ARCHIVO O CARPETA:

ELIMINAR_RUTA: ruta


PARA EJECUTAR:

EJECUTAR: archivo.py


PARA RESPONDER:

RESPUESTA:

texto

NO uses markdown.
NO uses bloques ```python.
NO expliques el procedimiento.
"""


    print("\n🤖 Analizando...\n")


    # ======================================
    # CONSULTA A GEMINI
    # ======================================

    try:

        respuesta = (
            cliente.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt
            )
        )

        resultado = (
            respuesta.text or ""
        ).strip()

    except Exception as e:

        resultado = (
            f"ERROR: {str(e)}"
        )


    # ======================================
    # MOSTRAR RESULTADO
    # ======================================

    print("\n====================================")
    print(resultado[:10000])
    print("====================================")


    # ======================================
    # GUARDAR INFORME
    # ======================================

    fecha = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    informe = (
        f"informes/informe_{fecha}.txt"
    )

    with open(
        informe,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(resultado)


    # ======================================
    # CREAR ARCHIVO
    # ======================================

    if resultado.startswith(
        "CREAR_ARCHIVO:"
    ):

        try:

            encabezado, contenido = (
                resultado.split(
                    "\n",
                    1
                )
            )

            ruta = encabezado.replace(
                "CREAR_ARCHIVO:",
                ""
            ).strip()

            crear_archivo(
                ruta,
                contenido
            )

            print(
                f"\n✅ Archivo creado: {ruta}"
            )

        except Exception as e:

            print(
                f"\n❌ Error creando archivo: {e}"
            )


    # ======================================
    # MODIFICAR ARCHIVO
    # ======================================

    elif resultado.startswith(
        "MODIFICAR_ARCHIVO:"
    ):

        try:

            encabezado, contenido = (
                resultado.split(
                    "\n",
                    1
                )
            )

            ruta = encabezado.replace(
                "MODIFICAR_ARCHIVO:",
                ""
            ).strip()

            print(
                f"\n📄 Modificando: {ruta}"
            )

            if existe_archivo(ruta):

                backup = (
                    f"backups/"
                    f"{os.path.basename(ruta)}."
                    f"{fecha}.bak"
                )

                original = leer_archivo(
                    ruta
                )

                with open(
                    backup,
                    "w",
                    encoding="utf-8"
                ) as copia:

                    copia.write(
                        original
                    )

                print(
                    f"💾 Backup: {backup}"
                )

            escribir_archivo(
                ruta,
                contenido
            )

            print(
                f"✅ Archivo actualizado: {ruta}"
            )

        except Exception as e:

            print(
                f"\n❌ Error modificando: {e}"
            )


    # ======================================
    # CREAR CARPETA
    # ======================================

    elif resultado.startswith(
        "CREAR_CARPETA:"
    ):

        try:
            ruta = resultado.split(":", 1)[1].strip()
            print(crear_carpeta(ruta))
        except Exception as e:
            print(f"\n❌ Error creando carpeta: {e}")


    # ======================================
    # MOVER O RENOMBRAR RUTA
    # ======================================

    elif resultado.startswith(
        "MOVER_RUTA:"
    ):

        try:
            especificacion = resultado.split(":", 1)[1].strip()
            origen, destino = especificacion.split("->", 1)
            print(mover_ruta(origen.strip(), destino.strip()))
        except Exception as e:
            print(f"\n❌ Error moviendo o renombrando: {e}")


    # ======================================
    # ELIMINAR RUTA
    # ======================================

    elif resultado.startswith(
        "ELIMINAR_RUTA:"
    ):

        ruta = resultado.split(":", 1)[1].strip()
        confirmacion = input(
            f"¿Confirmas eliminar '{ruta}'? Escribe SI para continuar: "
        )

        if confirmacion.strip().upper() == "SI":
            try:
                print(eliminar_ruta(ruta))
            except Exception as e:
                print(f"\n❌ Error eliminando: {e}")
        else:
            print("Eliminación cancelada.")


    # ======================================
    # EJECUTAR ARCHIVO
    # ======================================

    elif resultado.startswith(
        "EJECUTAR:"
    ):

        try:

            archivo = (
                resultado.replace(
                    "EJECUTAR:",
                    ""
                ).strip()
            )

            salida = (
                ejecutar_python(
                    archivo
                )
            )

            print(
                "\n=========== STDOUT ==========="
            )

            print(
                salida["stdout"]
            )

            print(
                "\n=========== STDERR ==========="
            )

            print(
                salida["stderr"]
            )

        except Exception as e:

            print(
                f"\n❌ Error ejecutando: {e}"
            )


    # ======================================
    # RESPUESTA NORMAL
    # ======================================

    else:

        print(
            "\nNo se detectó acción automática."
        )

        print(
            "Respuesta guardada como informe."
        )