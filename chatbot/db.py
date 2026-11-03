import re


def get_connection():
    from app import obtener_conexion

    return obtener_conexion()


def _consulta_lectura_acotada(query):
    query = str(query or "").strip()
    bloque = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", query, flags=re.IGNORECASE | re.DOTALL)
    if bloque:
        query = bloque.group(1).strip()
    if query.endswith(";"):
        query = query[:-1].rstrip()

    if not re.match(r"^SELECT\b", query, flags=re.IGNORECASE):
        raise ValueError("Solo se permiten consultas SELECT de lectura.")
    if ";" in query or re.search(r"--|#|/\*|\*/", query):
        raise ValueError("La consulta contiene sintaxis no permitida.")
    if re.search(
        r"\b(?:INTO\s+(?:OUTFILE|DUMPFILE)|FOR\s+UPDATE|LOCK\s+IN\s+SHARE\s+MODE|"
        r"SLEEP|BENCHMARK|LOAD_FILE|GET_LOCK|RELEASE_LOCK)\b",
        query,
        flags=re.IGNORECASE,
    ):
        raise ValueError("La consulta incluye una operación no permitida.")

    return f"SELECT * FROM ({query}) AS resultado_chatbot LIMIT 100"

def ejecutar_sql(query):
    consulta = _consulta_lectura_acotada(query)
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(consulta)
        return cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()