import sqlite3
import pandas as pd
DATABASE = 'cajeros_automaticos.db'

def print_all():
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM cajeros")
    i = 0
    for c in cursor:
        i+=1
        print(i)
        print(c)


def create_db():
    df = pd.read_csv('cajeros-automaticos.csv',sep=';',decimal=',')

    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    df.to_sql('cajeros',connection)
    query = "ALTER TABLE cajeros ADD COLUMN EXT_RESTANTES REAL;"
    cursor = connection.cursor()
    cursor.execute(query)

def set_1000():
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    query = "UPDATE cajeros SET EXT_RESTANTES = 1000.0;"
    cursor = connection.cursor()
    cursor.execute(query)
    connection.commit()

def sub_10():
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    query = "UPDATE cajeros SET EXT_RESTANTES = EXT_RESTANTES - 200;"
    cursor = connection.cursor()
    cursor.execute(query)
    connection.commit()

def list_columns():
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM sqlite_master")
    for c in cursor:
        print(c)
        print('\n\n')

def list_id():
    connection = sqlite3.connect(DATABASE)
    connection.text_factory = str
    cursor = connection.cursor()
    cursor.execute("SELECT EXT_RESTANTES,DOM_GEO,RED FROM cajeros WHERE EXT_RESTANTES < 1000")
    for c in cursor:
        print(c)
        print('\n')

list_id()

# create_db()
# sub_10()
# sub_10()
# sub_10()

# set_1000()
# print_all()
# exit(0)

# connection = sqlite3.connect(DATABASE)
# connection.text_factory = str
# cursor = connection.cursor()
# query = "SELECT * FROM cajeros WHERE RED = 'BANELCO' AND EXT_RESTANTES > 0;"
# cursor.execute(query)
# for c in cursor:
#     print(c)
