import mysql.connector

def connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="sam",
        password="pysideproject",
        database="invoicing"
    )
    return conn