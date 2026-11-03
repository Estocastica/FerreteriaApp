from chatbot.db import ejecutar_sql

try:

    resultados = ejecutar_sql("""
        SELECT
            id_producto,
            nombre,
            precio_venta,
            stock_actual
        FROM producto
        LIMIT 5
    """)

    print("\nCONEXIÓN EXITOSA\n")

    for fila in resultados:
        print(fila)

except Exception as e:

    print("\nERROR\n")
    print(e)