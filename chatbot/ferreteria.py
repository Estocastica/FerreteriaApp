import os
import sys
from pathlib import Path

from groq import Groq
from dotenv import load_dotenv

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chatbot.db import ejecutar_sql
from chatbot.prompts import SISTEMA, SCHEMA

load_dotenv()

MODELO = os.environ.get(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)
ARCHIVO_ENV = Path(__file__).resolve().parents[1] / ".env"


def _generar_texto(prompt):

    load_dotenv(ARCHIVO_ENV, override=False)

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "Falta configurar GROQ_API_KEY."
        )

    client = Groq(
        api_key=api_key
    )

    respuesta = client.chat.completions.create(
        model=MODELO,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    texto = respuesta.choices[0].message.content if respuesta.choices else None
    if not texto or not texto.strip():
        raise RuntimeError("Groq devolvió una respuesta vacía.")
    return texto.strip()


def generar_sql(pregunta):
    pregunta = str(pregunta or "").strip()
    if not pregunta:
        raise ValueError("Escribe una pregunta antes de consultar.")

    prompt = f"""{SISTEMA}
{SCHEMA}

Reglas obligatorias para esta consulta:
- Devuelve una sola sentencia SELECT de solo lectura.
- No uses comentarios, punto y coma, funciones de espera ni acceso a archivos.
- Limita los resultados a 100 filas cuando corresponda.
- Devuelve únicamente el SQL, sin bloques Markdown ni explicaciones.

Pregunta del usuario:
{pregunta}
"""
    return _generar_texto(prompt)


def responder_con_sql(pregunta):
    try:
        sql = generar_sql(pregunta)
    except Exception as error:
        raise RuntimeError("Groq no pudo generar la consulta SQL.") from error

    try:
        resultados = ejecutar_sql(sql)
    except Exception as error:
        raise RuntimeError("No se pudo ejecutar el SQL en la base de datos.") from error

    return sql, _resumir_resultados(resultados)


def _resumir_resultados(resultados):
    if not resultados:
        return "No encontré registros que coincidan con la consulta."

    etiquetas = {
        "id_producto": "ID de producto",
        "id_cliente": "ID de cliente",
        "id_venta": "ID de venta",
        "nombre": "Nombre",
        "producto": "Producto",
        "codigo": "Código",
        "stock_actual": "Stock actual",
        "stock_minimo": "Stock mínimo",
        "precio_venta": "Precio de venta",
        "total": "Total",
        "fecha": "Fecha",
        "cantidad": "Cantidad",
        "tipo": "Tipo",
        "limite_credito": "Límite de crédito",
        "saldo_pendiente": "Saldo pendiente",
    }
    cantidad_total = len(resultados)
    filas_visibles = resultados[:10]
    lineas = [f"La consulta devolvió {cantidad_total} resultado(s):"]

    for indice, fila in enumerate(filas_visibles, start=1):
        campos = []
        for columna, valor in fila.items():
            etiqueta = etiquetas.get(columna, columna.replace("_", " ").capitalize())
            if isinstance(valor, (int, float)) and any(
                palabra in columna.lower()
                for palabra in ("precio", "total", "saldo", "limite", "monto")
            ):
                valor_texto = f"${valor:,.2f}"
            else:
                valor_texto = str(valor)
            campos.append(f"{etiqueta}: {valor_texto}")
        lineas.append(f"{indice}. " + "; ".join(campos))

    if cantidad_total > len(filas_visibles):
        lineas.append(f"Se muestran 10 de {cantidad_total} resultados.")
    return "\n".join(lineas)


def responder(pregunta):
    return responder_con_sql(pregunta)[1]


def main():
    try:
        pregunta = input("¿Qué necesitas consultar? ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nConsulta cancelada.")
        return 1

    if not pregunta:
        print("Escribe una pregunta para continuar.")
        return 1

    try:
        print("Consultando la información...")
        sql, respuesta = responder_con_sql(pregunta)
    except Exception as error:
        print(f"No se pudo completar la consulta: {error}")
        return 1

    print("\nConsulta SQL ejecutada:\n")
    print(sql)
    print("\nRespuesta:\n")
    print(respuesta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
