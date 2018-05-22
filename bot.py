# - *- coding: utf- 8 - *-
import telegram
from telegram.ext import *
import geopy.distance
import sqlite3
from collections import namedtuple


TOKEN = '529475361:AAGlJG8JL8KTY2WQqgMccWx81Y7bySCm1ck'
DATABASE = 'cajeros_automaticos.db'

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

def cajeros_mas_cercanos(redDeCajeros, coordenadaOrigen, minDist=500, cota=3):
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    query = "SELECT DOM_GEO,BARRIO,BANCO,LAT,LNG \
            FROM cajeros WHERE RED =\'{}\' AND EXT_RESTANTES > 0;".format(redDeCajeros)
    cursor.execute(query)
    masCercanos = []
    for atm in cursor:
        distanciaAOrigen = geopy.distance.vincenty(coordenadaOrigen, (atm[3],atm[4]) ).m
        if distanciaAOrigen <= minDist:
            unCajero = {
                'direccion': atm[0],
                'barrio': atm[1],
                'banco': atm[2],
                'dist': distanciaAOrigen,
                'coordenadas': (atm[3],atm[4])
                }
            masCercanos.append(unCajero)
    masCercanos.sort(key= lambda tup: tup['dist'])
    return masCercanos[len(masCercanos)-cota:]

def registrar_extracciones(cajeros):
    querries = []
    if len(cajeros) == 3:
        query = "UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 0.7 WHERE;"

    elif len(cajeros) == 2:
    elif len(cajeros) == 1:
    else:
        print('ERROR: se están enviando más de 3 cajeros?')
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()

#######################################
#### ENVÍO Y RECEPCIÓN DE MENSAJES ####
#######################################

def solicitar_ubicacion(bot, update):
    keyboard = [[telegram.KeyboardButton(text="Share location", request_location=True)]]
    reply_markup = telegram.ReplyKeyboardMarkup(keyboard=keyboard)
    bot.send_message(chat_id=update.message.chat_id, text="Ok! Necesito tu ubicación", reply_markup=reply_markup)

def enviar_cajeros(bot, update, redDeCajeros):
    # Obtengo los cajeros cercanos
    coor = (update.message.location.latitude, update.message.location.longitude)
    cajeros = cajeros_mas_cercanos(redDeCajeros,coor, minDist=500, cota=3)
    if not cajeros:
        update.message.reply_text('No tenés cajeros {} cerca.'.format(redDeCajeros))
        return DEFAULT

    # Le envío la lista y el mapa
    mensaje = ''
    for atm in cajeros:
        mensaje += '\xF0\x9F\x92\xB0'+atm['direccion']+', '+atm['barrio']+' | '+atm['banco']+'\n'
    map_url = get_static_map_url(coor, [atm['coordenadas'] for atm in cajeros])
    bot.send_photo(chat_id=update.message.chat_id, photo=map_url)
    update.message.reply_text(mensaje)

    # Registro las extracciones
    return DEFAULT

def enviar_cajeros_link(bot, update):
    return enviar_cajeros(bot,update,'LINK')

def enviar_cajeros_banelco(bot, update):
    return enviar_cajeros(bot,update,'BANELCO')

# Comandos
def start(bot, update):
    update.message.reply_text("Hola! Soy el bot de cajeros de CABA.")
    return DEFAULT

def link(bot, update):
    solicitar_ubicacion(bot, update)
    return LINK_ESPERANDO_UBICACION

def banelco(bot, update):
    solicitar_ubicacion(bot, update)
    return BANELCO_ESPERANDO_UBICACION

def cancel(bot, update):
    return DEFAULT

def error_callback(bot, update, error):
    print('ERROR!')

def main():

    # Create Updater object and attach dispatcher to it
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    print("Bot started")

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states= {
            DEFAULT:
                [CommandHandler('link', link),CommandHandler('banelco', banelco)],
            LINK_ESPERANDO_UBICACION:
                [MessageHandler(Filters.location, enviar_cajeros_link)],
            BANELCO_ESPERANDO_UBICACION:
                [MessageHandler(Filters.location, enviar_cajeros_banelco)]
            },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(error_callback)

    # Start the bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()

if __name__ == '__main__':
    main()
