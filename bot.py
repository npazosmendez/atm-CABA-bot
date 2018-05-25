# - *- coding: utf- 8 - *-
import telegram
from telegram.ext import *
import time
import schedule
import signal
import os, sys
import logging
from datamanagement import *

TOKEN_PATH = 'token.txt'
LOG_PATH = 'botLog.log'


####################
#### AUXILIARES ####
####################

def get_static_map_url(central_marker, other_markers=[]):
    """
    Obtiene la URL de un mapa estático de Google Maps, con un marcador
    distinguido 'central_marker' y otros agregados opcionales.
    """
    url = 'https://maps.googleapis.com/maps/api/staticmap'
    url += '?size=600x300'
    url += '&markers=color:red|'+str(central_marker[0])+','+str(central_marker[1])
    for coor in other_markers:
        url += '&markers=color:blue|label:A|'+str(coor[0])+','+str(coor[1])
    return url

def network_try(closure, max_retries = 3):
    """
    Intenta ejecutar 'closure', reintentando hasta 'max_retries' veces en
    casos de fallo de red, según las excepciones de telegram.
    """
    for i in range(max_retries):
        if i > 0:
            logging.error('Retrying')
        try:
            closure()
        except (telegram.error.TimedOut, telegram.error.NetworkError) as e:
            logging.error(str(e))
            continue
        break


###########################
#### ENVÍO DE MENSAJES ####
###########################

def solicitar_ubicacion(bot, update):
    """
    Le pide la ubicación al usuario, que debe enviarla voluntariamente
    presionando el botón.
    """
    keyboard = [[telegram.KeyboardButton(text="Share location", request_location=True)]]
    reply_markup = telegram.ReplyKeyboardMarkup(keyboard=keyboard)
    def send_msg():
        bot.send_message(chat_id=update.message.chat_id, text="¡Ok! Mandame tu ubicación", reply_markup=reply_markup)
    network_try(send_msg)

def enviar_cajeros(bot, update, red_de_cajeros):
    """
    Le envía al usuario los cajeros cercanos de la red 'red_de_cajeros' y
    el respectivo mapa. Además, registra las extracciones.
    """
    # Obtengo los cajeros cercanos
    coor = (update.message.location.latitude, update.message.location.longitude)
    logging.info('Buscando cajeros '+red_de_cajeros+' @ '+str(coor))
    cajeros_cercanos = cajeros_mas_cercanos(red_de_cajeros,coor, distancia_minima=500, cota=3)

    # Si no tiene cajeros, le digo
    if not cajeros_cercanos:
        def send_msg():
            update.message.reply_text('No tenés cajeros {} cerca.'.format(red_de_cajeros))
            logging.info('No se encontraron cajeros.')
        network_try(send_msg)
        return DEFAULT

    # Si tiene, le envío la lista y el mapa
    mensaje = ''
    for atm in cajeros_cercanos:
        mensaje += '\xF0\x9F\x92\xB0'+atm.direccion+', '+atm.barrio+' | '+atm.banco+'\n'
    map_url = get_static_map_url(coor, [(atm.latitud,atm.longitud) for atm in cajeros_cercanos])
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
    registrar_extracciones(cajeros_cercanos)

#############################
#### COMANDOS Y HANDLERS ####
#############################

# Estados de una conversación
DEFAULT, LINK_ESPERANDO_UBICACION, BANELCO_ESPERANDO_UBICACION = range(3)

def enviar_cajeros_link(bot, update):
    # @ LINK_ESPERANDO_UBICACION
    enviar_cajeros(bot,update,'LINK')
    return DEFAULT

def enviar_cajeros_banelco(bot, update):
    # @ BANELCO_ESPERANDO_UBICACION
    enviar_cajeros(bot,update,'BANELCO')
    return DEFAULT

def cancel(bot, update):
    return DEFAULT

def bot_help(bot, update):
    # @ DEFAULT
    def send_msg():
        update.message.reply_text("¡Hola! Soy el bot de cajeros de CABA. Usá los comandos /link o /banelco para encontrar cajeros cerca tuyo, y /help para repetir este mensaje.")
    network_try(send_msg)
    return DEFAULT

def link(bot, update):
    # @ DEFAULT
    logging.info('Recibido /link')
    solicitar_ubicacion(bot, update)
    return LINK_ESPERANDO_UBICACION

def banelco(bot, update):
    # @ DEFAULT
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

##############
#### MAIN ####
##############

def main():
    # Logging config
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # Log file
    logging.basicConfig(filename=LOG_PATH)
    # Console log
    cout = logging.StreamHandler(sys.stdout)
    logger.addHandler(cout)


    # Handler de CTRL+C (para matar todos los threads)
    def abort(signal, frame):
        print('Aborted.')
        os._exit(0)
    signal.signal(signal.SIGINT, abort)


    ## Configuración del bot
    with open(TOKEN_PATH, 'r') as file:
        TOKEN = file.readline()[:-1]
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

    ## Iniciar el bot (otro thread)
    updater.start_polling()
    logging.info('Bot iniciado')

    ## Programar actualización de base de datos
    schedule.every().monday.at("8:00").do(reabastecer_cajeros)
    schedule.every().tuesday.at("8:00").do(reabastecer_cajeros)
    schedule.every().wednesday.at("8:00").do(reabastecer_cajeros)
    schedule.every().thursday.at("8:00").do(reabastecer_cajeros)
    schedule.every().friday.at("12:58").do(reabastecer_cajeros)

    ## Verificar actualizaciones cada 5 minutos
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()
