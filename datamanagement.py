# - *- coding: utf- 8 - *-
import sqlite3
from geopy.distance import vincenty
from collections import namedtuple
import logging
import time

DATABASE = 'cajeros_automaticos.db'

Cajero = namedtuple('Cajero', 'id, direccion, barrio, banco, latitud, longitud')

def cajeros_mas_cercanos(red_de_cajeros, origen, distancia_minima=500, cota=3):
    """
    Devuelve una lista de los cajeros más cercanos a 'origen' de la red 'red_de_cajeros'.
    'distancia_minima' es el rango de búsqueda geográfico en metros, y 'cota' una cota para
    la cantidad de cajeros devueltos.
    """
    # Busco los cajeros de la red que tengan extracciones restantes
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    query = "SELECT ID,DOM_GEO,BARRIO,BANCO,LAT,LNG \
            FROM cajeros WHERE RED =\'{}\' AND EXT_RESTANTES > 0;".format(red_de_cajeros)
    cursor.execute(query)

    # Me guardo solo aquellos que estén cerca
    masCercanos = []
    for atm in map(Cajero._make, cursor.fetchall() ):
        dist = vincenty(origen, (atm.latitud,atm.longitud) ).m
        if dist <= distancia_minima:
            masCercanos.append( (atm, dist) )

    # Devuelvo los top-cota más cercanos
    masCercanos.sort(key= lambda tup: tup[1])
    masCercanos = masCercanos[0:cota]
    return [t[0] for t in masCercanos]


def registrar_extracciones(cajeros):
    """
    Registra extracciones de los cajeros indicados, suponiendo que vienen de una consulta
    única del bot y siguiendo la información probabilística que se tiene.
    """
    queries = []
    # La proporción de extracciones depende de la cantidad de cajeros consultados
    if len(cajeros) == 3:
        # 3 cajeros cerca -> 70%, 20%, 10%
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.7 WHERE ID = {};".format(str(cajeros[0].id)))
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.2 WHERE ID = {};".format(str(cajeros[1].id)))
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.1 WHERE ID = {};".format(str(cajeros[2].id)))
    elif len(cajeros) == 2:
        # 2 cajeros cerca -> 70%, 30%
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.7 WHERE ID = {};".format(str(cajeros[0].id)))
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.3 WHERE ID = {};".format(str(cajeros[1].id)))
    elif len(cajeros) == 1:
        # 1 cajero cerca -> 100%
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 1 WHERE ID = {};".format(str(cajeros[0].id)))
    else:
        print('ERROR: se están enviando más de 3 cajeros?')
        logging.error('se están enviando más de 3 cajeros?')

    # Ejecuto las queries  y comiteo
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    log = 'actualizando entradas:'
    for q in queries:
        log += '\n'+q
        cursor.execute(q)
    logging.info(log)
    connection.commit()

def reabastecer_cajeros():
    """
    Reabastece todos los cajeros de la base de datos, estableciendo sus extracciones
    restantes en 1000.
    """
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    cursor.execute("UPDATE cajeros SET EXT_RESTANTES = 1000.0;")
    connection.commit()
    logging.info('Cajeros reabastecidos @'+time.strftime("%c"))
