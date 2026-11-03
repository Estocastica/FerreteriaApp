from chatbot.ferreteria import responder_con_sql


def main():
	pregunta = input("¿Qué necesitas consultar? ").strip()
	if not pregunta:
		print("Escribe una pregunta para continuar.")
		return 1

	try:
		print("Consultando la información...")
		sql, respuesta = responder_con_sql(pregunta)
		print("\nConsulta SQL ejecutada:\n")
		print(sql)
		print("\nRespuesta:\n")
		print(respuesta)
		return 0
	except Exception:
		print("No se pudo completar la consulta. Revisa las variables de entorno, Gemini y MySQL.")
		return 1


if __name__ == "__main__":
	raise SystemExit(main())