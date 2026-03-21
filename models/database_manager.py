from models.database.tables import Tables

class DatabaseManager(Tables):
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

    def fetch_all(self):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute(f"SELECT * FROM {self.table_name}")
            return cursor.fetchall()
        finally:
            cursor.close()

    def insert_type(self, name: str):
        cursor = self.conn.cursor()
        try:
            query = "INSERT INTO product_type (product_type_name) VALUES (%s)"
            cursor.execute(query, (name,))
            self.conn.commit()
        finally:
            cursor.close()

    def delete_type(self, type_id: int):
        cursor = self.conn.cursor()
        try:
            query = "DELETE FROM product_type WHERE id = %s"
            cursor.execute(query, (type_id,))
            self.conn.commit()
        finally:
            cursor.close()

    def get_products_by_type(self, type_id):
        self.cursor.execute("SELECT id, product_name, ref_b_analyse, num_act, physico, toxico, micro, subtotal FROM products WHERE product_type_id=%s", (type_id,))
        return self.cursor.fetchall()
    
    def add_product(self, type_id, product_name, ref="0", num_act="0", physico="0", toxico="0", micro="0", subtotal="0"):
        self.cursor.execute(
            "INSERT INTO products (product_type_id, product_name, ref_b_analyse, num_act, physico, toxico, micro, subtotal) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (type_id, product_name, ref, num_act, physico, toxico, micro, subtotal)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def delete_product(self, product_id):
        self.cursor.execute("DELETE FROM products WHERE id=%s", (product_id,))
        self.conn.commit()
    
    def update_product(self, product_id, ref, num_act, physico, toxico, micro, subtotal):
        self.cursor.execute(
            "UPDATE products SET ref_b_analyse=%s, num_act=%s, physico=%s, toxico=%s, micro=%s, subtotal=%s WHERE id=%s",
            (ref, num_act, physico, toxico, micro, subtotal, product_id)
        )
        self.conn.commit()

  