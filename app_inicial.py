import os
import secrets
from decimal import Decimal, InvalidOperation
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template_string, request, url_for, get_flashed_messages


load_dotenv(Path(__file__).resolve().with_name(".env"))

app = Flask(__name__)
app.secret_key = os.environ.get("FERRETERIA_SECRET_KEY") or secrets.token_hex(32)


def conectar_bd():
    variables = {
        "host": ("MYSQL_ADDON_HOST", "MYSQLHOST", "MYSQL_HOST"),
        "port": ("MYSQL_ADDON_PORT", "MYSQLPORT", "MYSQL_PORT"),
        "user": ("MYSQL_ADDON_USER", "MYSQLUSER", "MYSQL_USER"),
        "password": ("MYSQL_ADDON_PASSWORD", "MYSQLPASSWORD", "MYSQL_PASSWORD"),
        "database": ("MYSQL_ADDON_DB", "MYSQLDATABASE", "MYSQL_DATABASE"),
    }
    config = {
        key: next((os.environ[name] for name in aliases if os.environ.get(name)), None)
        for key, aliases in variables.items()
    }
    faltantes = [key for key, value in config.items() if value is None and key != "port"]
    if faltantes:
        names = ", ".join(variables[key][0] for key in faltantes)
        raise RuntimeError(f"Faltan variables MySQL: {names}. Configúralas en .env.")

    return mysql.connector.connect(
        host=config["host"],
        port=int(config["port"] or 3306),
        user=config["user"],
        password=config["password"],
        database=config["database"],
        connection_timeout=10,
    )


@app.route("/")
def inicio():
    return redirect(url_for("nuevo_producto"))


@app.route("/productos/nuevo", methods=["GET", "POST"])
def nuevo_producto():
    conexion = None
    cursor = None
    categorias = []

    try:
        conexion = conectar_bd()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id_categoria, nombre FROM categoria ORDER BY nombre")
        categorias = cursor.fetchall()

        if request.method == "POST":
            id_categoria = request.form.get("id_categoria", "").strip()
            codigo = request.form.get("codigo", "").strip()
            nombre = request.form.get("nombre", "").strip()
            precio_texto = request.form.get("precio_venta", "").strip()
            stock_texto = request.form.get("stock_actual", "").strip()
            minimo_texto = request.form.get("stock_minimo", "").strip()

            try:
                categoria = int(id_categoria)
                precio = Decimal(precio_texto)
                stock = int(stock_texto)
                stock_minimo = int(minimo_texto)

                if not codigo or not nombre or categoria <= 0:
                    raise ValueError("Completa código, nombre y categoría.")
                if not precio.is_finite() or precio < 0:
                    raise ValueError("El precio debe ser válido y no negativo.")
                if stock < 0 or stock_minimo < 0:
                    raise ValueError("El stock actual y el mínimo no pueden ser negativos.")

                cursor.execute("""
                    INSERT INTO producto
                        (id_categoria, codigo, nombre, precio_venta, stock_actual, stock_minimo)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (categoria, codigo, nombre, precio, stock, stock_minimo))
                conexion.commit()
                flash("Producto registrado correctamente.", "success")
                return redirect(url_for("nuevo_producto"))
            except (InvalidOperation, ValueError) as error:
                conexion.rollback()
                flash(str(error), "danger")
            except mysql.connector.Error as error:
                conexion.rollback()
                flash(f"No se pudo registrar el producto: {error}", "danger")
    except (RuntimeError, mysql.connector.Error) as error:
        flash(f"No se pudo conectar con MySQL: {error}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conexion:
            conexion.close()

    mensajes = get_flashed_messages(with_categories=True)
    plantilla = """<!doctype html>
    <html lang="es"><head>
        <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Nuevo producto</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head><body class="bg-light">
        <main class="container py-5" style="max-width: 760px">
            <h1 class="h3 mb-4">Registrar producto</h1>
            {% for categoria, mensaje in mensajes %}
                <div class="alert alert-{{ categoria }}" role="alert">{{ mensaje }}</div>
            {% endfor %}
            {% if not categorias %}
                <div class="alert alert-warning">No hay categorías disponibles o no se pudo consultar la base.</div>
            {% endif %}
            <section class="card border-0 shadow-sm"><div class="card-body p-4">
                <form method="post" action="{{ url_for('nuevo_producto') }}">
                    <div class="mb-3"><label class="form-label" for="id_categoria">Categoría</label>
                        <select id="id_categoria" name="id_categoria" class="form-select" required>
                            <option value="">Selecciona una categoría</option>
                            {% for categoria in categorias %}<option value="{{ categoria['id_categoria'] }}">{{ categoria['nombre'] }}</option>{% endfor %}
                        </select>
                    </div>
                    <div class="mb-3"><label class="form-label" for="codigo">Código</label>
                        <input id="codigo" name="codigo" class="form-control" maxlength="50" required>
                    </div>
                    <div class="mb-3"><label class="form-label" for="nombre">Nombre del producto</label>
                        <input id="nombre" name="nombre" class="form-control" maxlength="150" required>
                    </div>
                    <div class="row g-3">
                        <div class="col-md-4"><label class="form-label" for="precio_venta">Precio de venta</label>
                            <input id="precio_venta" name="precio_venta" type="number" min="0" step="0.01" class="form-control" required>
                        </div>
                        <div class="col-md-4"><label class="form-label" for="stock_actual">Stock actual</label>
                            <input id="stock_actual" name="stock_actual" type="number" min="0" step="1" class="form-control" value="0" required>
                        </div>
                        <div class="col-md-4"><label class="form-label" for="stock_minimo">Stock mínimo</label>
                            <input id="stock_minimo" name="stock_minimo" type="number" min="0" step="1" class="form-control" value="5" required>
                        </div>
                    </div>
                    <button class="btn btn-primary mt-4" type="submit">Guardar producto</button>
                </form>
            </div></section>
        </main>
    </body></html>"""
    return render_template_string(plantilla, categorias=categorias, mensajes=mensajes)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
