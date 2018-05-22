# - *- coding: utf- 8 - *-
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler
from telegram.ext import *
from telegram.error import *
import telegram
import geopy.distance

import pandas as pd
import sqlite3


TOKEN = '529475361:AAGlJG8JL8KTY2WQqgMccWx81Y7bySCm1ck'
DATABASE = 'miBase.db'

DEFAULT, LINK_ESPERANDO_UBICACION, BANELCO_ESPERANDO_UBICACION = range(3)


def get_static_map_url(markerCentral, otrosMarkers=[]):
	url = 'https://maps.googleapis.com/maps/api/staticmap'
	url += '?size=600x300'
	url += '&markers=color:red|label:S|'+str(markerCentral[0])+','+str(markerCentral[1])
	for coor in otrosMarkers:
		url += '&markers=color:blue|'+str(coor[0])+','+str(coor[1])
	return url


def cajeros_mas_cercanos(redDeCajeros, coordenadaOrigen, minDist=500, cota=3):
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    query = "SELECT DOM_GEO,BARRIO,BANCO,LAT,LNG \
            FROM cajeros WHERE RED =\'{}\';".format(redDeCajeros)
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
    print(masCercanos)
    masCercanos.sort(key= lambda tup: tup['dist'])
    return masCercanos[len(masCercanos)-cota:]


# print(cajeros_mas_cercanos('BANELCO', (-34.55323,-58.45141) ))
# exit(0)


# def cajeros_mas_cercanos(redDeCajeros, coordenadaOrigen, minDist=500, cota=3):
#     masCercanos = []
#     for index, row in cajeros_df.iterrows():
#         if row['RED'] == redDeCajeros:
#             distanciaAOrigen = geopy.distance.vincenty(coordenadaOrigen, (row['LAT'],row['LNG']) ).m
#             if distanciaAOrigen <= minDist:
#                 unCajero = {
#                     'direccion': row['DOM_GEO'],
#                     'barrio': row['BARRIO'],
#                     'banco': row['BANCO'],
#                     'dist': distanciaAOrigen,
#                     'coordenadas': (row['LAT'],row['LNG'])
#                     }
#                 masCercanos.append(unCajero)
#     masCercanos.sort(key= lambda tup: tup['dist'])
#     return masCercanos[len(masCercanos)-cota:]


def solicitar_ubicacion(bot, update):
    keyboard = [[telegram.KeyboardButton(text="Share location", request_location=True)]]
    reply_markup = telegram.ReplyKeyboardMarkup(keyboard=keyboard)
    bot.send_message(chat_id=update.message.chat_id, text="Ok! Necesito tu ubicación", reply_markup=reply_markup)

def start(bot, update):
    update.message.reply_text("Hola! Soy el bot de cajeros de CABA.")
    return DEFAULT

def mostrar_cajeros_link(bot, update):
    coor = (update.message.location.latitude,    update.message.location.longitude)
    cajeros = cajeros_mas_cercanos('LINK',coor, minDist=500, cota=3)
    if not cajeros:
        update.message.reply_text('No tenés cajeros Link cerca.')
        return
    mensaje = ''
    for atm in cajeros:
        mensaje += '\xF0\x9F\x92\xB0'+atm['direccion']+', '+atm['barrio']+' | '+atm['banco']+'\n'
    update.message.reply_text(mensaje)
    print(mensaje)
    return DEFAULT

def mostrar_cajeros_banelco(bot, update):
    print('muestrando cajeros banelco')
    coor = (update.message.location.latitude,    update.message.location.longitude)
    cajeros = cajeros_mas_cercanos('BANELCO',coor, minDist=500, cota=3)
    print(cajeros)
    mensaje = ''
    for atm in cajeros:
        mensaje += '\xF0\x9F\x92\xB0'+atm['direccion']+', '+atm['barrio']+' | '+atm['banco']+'\n'
    map_url = get_static_map_url(coor, [atm['coordenadas'] for atm in cajeros])
    bot.send_photo(chat_id=update.message.chat_id, photo=map_url)
    update.message.reply_text(mensaje)
    return DEFAULT

def link(bot, update):
    solicitar_ubicacion(bot, update)
    return LINK_ESPERANDO_UBICACION

def cancel(bot, update):
	pritn('cancelado')
	return DEFAULT

def banelco(bot, update):
    solicitar_ubicacion(bot, update)
    return BANELCO_ESPERANDO_UBICACION







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
                [MessageHandler(Filters.location, mostrar_cajeros_link)],
            BANELCO_ESPERANDO_UBICACION:
                [MessageHandler(Filters.location, mostrar_cajeros_banelco)]
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
