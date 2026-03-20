from models.database.tables import Tables

class DatabaseManagement(Tables):
    table_name = ""

    @classmethod
    def create_tables(cls):
        db = cls()
        try:
            db.proforma_invoice_table()
            db.standard_invoice_table()
            db.product_type_table()
            db.products_table()
        finally:
            db.close()

    @classmethod
    def get_all(cls):
        db = cls()
        cursor = db.conn.cursor(dictionary=True)  # curseur dict
        try:
            cursor.execute(f"SELECT * FROM {cls.table_name}")
            data = cursor.fetchall()
            return data
        finally:
            db.close()


    @classmethod
    def fetch_row(cls, target_column, filter_column, filter_value):
        db = cls()
        cursor = db.conn.cursor(dictionary=True)  # curseur dict
        try:
            query = f"SELECT {target_column} FROM {cls.table_name} WHERE {filter_column} = %s"
            cursor.execute(query, (filter_value,))
            row = cursor.fetchone()
            return row
        finally:
            db.close()


    @classmethod
    def insert(cls, data):
        db = cls()
        cursor = db.cursor
        try:
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["%s"] * len(data))
            query = f"INSERT INTO {cls.table_name} ({columns}) VALUES ({placeholders})"
            cursor.execute(query, tuple(data.values()))
            db.conn.commit()
        finally:
            db.close()

    @classmethod
    def delete(cls, where):
        db = cls()
        cursor = db.cursor
        try:
            conditions = " AND ".join([f"{col} = %s" for col in where.keys()])
            query = f"DELETE FROM {cls.table_name} WHERE {conditions}"
            cursor.execute(query, tuple(where.values()))
            db.conn.commit()
        finally:
            db.close()

    @classmethod
    def update(cls, data, where):
        db = cls()
        cursor = db.cursor
        try:
            set_clause = ", ".join([f"{col} = %s" for col in data.keys()])
            conditions = " AND ".join([f"{col} = %s" for col in where.keys()])
            query = f"UPDATE {cls.table_name} SET {set_clause} WHERE {conditions}"
            values = list(data.values()) + list(where.values())
            cursor.execute(query, values)
            db.conn.commit()
        finally:
            db.close()
