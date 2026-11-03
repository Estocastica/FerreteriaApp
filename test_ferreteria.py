from chatbot.ferreteria import responder


def main():
	pregunta = input("¿Qué necesitas? ").strip()
	if pregunta:
		print(responder(pregunta))
	else:
		print("Escribe una pregunta para continuar.")


if __name__ == "__main__":
	main()