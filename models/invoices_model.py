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
        cursor.execute(f"SELECT * FROM {cls.table_name}")
        
        data = cursor.fetchall()
        conn.close()
        return data