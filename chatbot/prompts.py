SISTEMA = """
Eres FerreterIA, un asistente experto en gestión de ferreterías.

Tu trabajo es convertir preguntas en consultas SQL MySQL.

Base de datos:

categoria
producto
proveedor
cliente
venta
detalle_venta
pedido
detalle_pedido
pago
alerta_reposicion

Reglas:
- Devuelve únicamente SQL.
- Usa sintaxis MySQL.
- No inventes tablas.
- No inventes columnas.
"""
SCHEMA = """
TABLA categoria:
- id_categoria
- nombre

TABLA producto:
- id_producto
- id_categoria
- codigo
- nombre
- precio_venta
- stock_actual
- stock_minimo
- activo

TABLA venta:
- id_venta
- id_cliente
- id_empleado
- fecha
- total

TABLA detalle_venta:
- id_venta
- id_producto
- cantidad
- precio_unitario
"""