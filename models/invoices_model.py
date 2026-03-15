from models.database.connection import connection

class InvoicesModel:
    table_name = ""

    @classmethod
    def get_all(cls):
        """
        Returns all rows in the table as a list of dictionaries.
        """
        conn = connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("USE invoicing")
        cursor.execute(f"SELECT * FROM {cls.table_name}")

        
        data = cursor.fetchall()
        conn.close()
        return data
    
    @classmethod
    def insert(cls, data):
        """
        Insert a row into the table.
        data must be a dictionary.
        """
        conn = connection()
        cursor = conn.cursor()
        cursor.execute("use invoicing")

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))

        query = f"""
        INSERT INTO {cls.table_name} ({columns})
        VALUES ({placeholders})
        """

        cursor.execute(query, tuple(data.values()))
        conn.commit()
        conn.close()
