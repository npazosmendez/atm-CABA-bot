Un bot para Telegram que busca cajeros cercanos al usuario. Fue parte de una evaluación para un puesto de trabajo, a modo de entrevista técnica.

# Sobre el funcionamiento del bot
Basta con correr el script 'bot.py', se usa el token en 'token.dat'.

# Sobre el registro de extracciones
Para estimar las extracciones restantes de un cajero, una consulta al bot de telegram se considera como una única extracción repartida entre todos los cajeros que se enviaron.

Por ejemplo, si se envían 3 cajeros A,B,C (en ese orden por distancia), se cuenta:
	* 0,7 extracciones en A
	* 0,2 extracciones en B
	* 0,1 extracciones en C

Otra heurística podría haber sido elegir un cajero entre A, B y C con las probabilidades correspondientes. El comportamiento asintótico es el mismo.
