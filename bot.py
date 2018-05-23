# - *- coding: utf- 8 - *-
import telegram
from telegram.ext import *
from geopy.distance import vincenty
import sqlite3
from collections import namedtuple
import time
import schedule
import logging
import signal
import os, sys


TOKEN = '529475361:AAGlJG8JL8KTY2WQqgMccWx81Y7bySCm1ck'
DATABASE = 'cajeros_automaticos.db'
def abort(signal, frame):
        print('Aborted.')
        os._exit(0)

# Estados de conversación
DEFAULT, LINK_ESPERANDO_UBICACION, BANELCO_ESPERANDO_UBICACION = range(3)

Cajero = namedtuple('Cajero', 'id, direccion, barrio, banco, latitud, longitud')

########################################
######## UTILIDADES AUXILIARES ########
#######################################

def get_static_map_url(markerCentral, otrosMarkers=[]):
    url = 'https://maps.googleapis.com/maps/api/staticmap'
    url += '?size=600x300'
    url += '&markers=color:red|'+str(markerCentral[0])+','+str(markerCentral[1])
    for coor in otrosMarkers:
        url += '&markers=color:blue|label:A|'+str(coor[0])+','+str(coor[1])
    return url

def cajeros_mas_cercanos(redDeCajeros, origen, minDist=500, cota=3):
    # (-34.55323, -58.45141)
    # Busco los cajeros de la red que tengan extracciones restantes
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    query = "SELECT ID,DOM_GEO,BARRIO,BANCO,LAT,LNG \
            FROM cajeros WHERE RED =\'{}\' AND EXT_RESTANTES > 0;".format(redDeCajeros)
    cursor.execute(query)

    # Me guardo solo aquellos que estén cerca
    masCercanos = []
    for atm in map(Cajero._make, cursor.fetchall() ):
        dist = vincenty(origen, (atm.latitud,atm.longitud) ).m
        if dist <= minDist:
            masCercanos.append( (atm, dist) )

    # Devuelvo los top-cota más cercanos
    masCercanos.sort(key= lambda tup: tup[1])
    masCercanos = masCercanos[0:cota]
    return [t[0] for t in masCercanos]


def registrar_extracciones(cajeros):
    queries = []
    # La proporción de extracciones depende de la cantidad de cajeros
    if len(cajeros) == 3:
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.7 WHERE ID = {};".format(str(cajeros[0].id)))
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.2 WHERE ID = {};".format(str(cajeros[1].id)))
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.1 WHERE ID = {};".format(str(cajeros[2].id)))
    elif len(cajeros) == 2:
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.7 WHERE ID = {};".format(str(cajeros[0].id)))
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.3 WHERE ID = {};".format(str(cajeros[1].id)))
    elif len(cajeros) == 1:
        queries.append("UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 1 WHERE ID = {};".format(str(cajeros[0].id)))
    else:
        print('ERROR: se están enviando más de 3 cajeros?')

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
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    cursor.execute("UPDATE cajeros SET EXT_RESTANTES = 1000.0;")
    connection.commit()
    logging.info('Cajeros reabastecidos @'+time.strftime("%c"))


#######################################
#### ENVÍO Y RECEPCIÓN DE MENSAJES ####
#######################################

def network_try(aClosure, maxReries = 3):
    for i in range(maxReries):
        if i > 0:
            logging.error('Retrying')
        try:
            aClosure()
        except (telegram.error.TimedOut, telegram.error.NetworkError) as e:
            logging.error(str(e))
            continue
        break

def solicitar_ubicacion(bot, update):
    keyboard = [[telegram.KeyboardButton(text="Share location", request_location=True)]]
    reply_markup = telegram.ReplyKeyboardMarkup(keyboard=keyboard)
    def send_msg():
        bot.send_message(chat_id=update.message.chat_id, text="¡Ok! Mandame tu ubicación", reply_markup=reply_markup)
    network_try(send_msg)

def enviar_cajeros(bot, update, redDeCajeros):
    # Obtengo los cajeros cercanos
    coor = (update.message.location.latitude, update.message.location.longitude)
    logging.info('Buscando cajeros '+redDeCajeros+' @ '+str(coor))
    cajeros = cajeros_mas_cercanos(redDeCajeros,coor, minDist=500, cota=3)

    # Si no tiene cajeros, le digo
    if not cajeros:
        def send_msg():
            update.message.reply_text('No tenés cajeros {} cerca.'.format(redDeCajeros))
            logging.info('No se encontraron cajeros.')
        network_try(send_msg)
        return DEFAULT

    # Si tiene, le envío la lista y el mapa
    mensaje = ''
    for atm in cajeros:
        mensaje += '\xF0\x9F\x92\xB0'+atm.direccion+', '+atm.barrio+' | '+atm.banco+'\n'
    map_url = get_static_map_url(coor, [(atm.latitud,atm.longitud) for atm in cajeros])
    logging.info('Intentando enviar cajeros y mapa')
    logging.info(mensaje)
    logging.info(map_url)
    def send_img():
        bot.send_photo(chat_id=update.message.chat_id, photo=map_url)
    def send_msg():
        update.message.reply_text(mensaje)
    network_try(send_img)
    network_try(send_msg)

    # Registro las extracciones
    registrar_extracciones(cajeros)

    return DEFAULT

def enviar_cajeros_link(bot, update):
    return enviar_cajeros(bot,update,'LINK')

def enviar_cajeros_banelco(bot, update):
    return enviar_cajeros(bot,update,'BANELCO')

def cancel(bot, update):
    return DEFAULT

# Comandos
def bot_help(bot, update):
    def send_msg():
        update.message.reply_text("¡Hola! Soy el bot de cajeros de CABA. Usá los comandos /link o /banelco para encontrar cajeros cerca tuyo, y /help para repetir este mensaje.")
    network_try(send_msg)
    return DEFAULT

def link(bot, update):
    logging.info('Recibido /link')
    solicitar_ubicacion(bot, update)
    return LINK_ESPERANDO_UBICACION

def banelco(bot, update):
    logging.info('Recibido /banelco')
    solicitar_ubicacion(bot, update)
    return BANELCO_ESPERANDO_UBICACION

def error_callback(bot, update, error):
    print('ERROR!')
    try:
        raise error
    except:
        print(error)
    logging.error(str(error))

def main():
    # Logging config
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # Log file
    logging.basicConfig(filename='botLog.log')
    # Console log
    cout = logging.StreamHandler(sys.stdout)
    logger.addHandler(cout)

    # Handler de CTRL+C (para matar todos los threads)
    signal.signal(signal.SIGINT, abort)

    # Configuración del bot
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.all, bot_help)],
        states= {
            DEFAULT:
                [CommandHandler('link', link),CommandHandler('banelco', banelco),CommandHandler('help',bot_help)],
            LINK_ESPERANDO_UBICACION:
                [MessageHandler(Filters.location, enviar_cajeros_link)],
            BANELCO_ESPERANDO_UBICACION:
                [MessageHandler(Filters.location, enviar_cajeros_banelco)]
            },
        fallbacks=[CommandHandler('cancel', cancel),MessageHandler(Filters.all, cancel)]
    )
    dispatcher.add_handler(conv_handler)
    # Handler de errores
    dispatcher.add_error_handler(error_callback)

    # Iniciar el bot (otro thread)
    updater.start_polling()
    logging.info('Bot iniciado')

    # Programar actualización de base de datos
    schedule.every().monday.at("8:00").do(reabastecer_cajeros)
    schedule.every().tuesday.at("8:00").do(reabastecer_cajeros)
    schedule.every().wednesday.at("8:00").do(reabastecer_cajeros)
    schedule.every().thursday.at("8:00").do(reabastecer_cajeros)
    schedule.every().friday.at("8:00").do(reabastecer_cajeros)

    # Verificar actualizaciones cada 5 minutos
    while True:
        schedule.run_pending()
        time.sleep(300)


if __name__ == '__main__':
    main()
