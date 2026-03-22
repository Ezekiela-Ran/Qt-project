from models.database.tables import Tables
import mysql.connector

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
            db.invoice_client_table()
            db.migrate_tables()  # Ajouter les colonnes manquantes
        finally:
            db.close()

    def migrate_tables(self):
        # Migration pour ajouter les colonnes manquantes si elles n'existent pas
        try:
            self.cursor.execute("ALTER TABLE standard_invoice ADD COLUMN total DECIMAL(10,2) DEFAULT 0")
        except mysql.connector.Error as e:
            if e.errno not in (1060, 1061):  # Column already exists or duplicate key
                raise
        
        try:
            self.cursor.execute("ALTER TABLE proforma_invoice ADD COLUMN total DECIMAL(10,2) DEFAULT 0")
        except mysql.connector.Error as e:
            if e.errno not in (1060, 1061):  # Column already exists or duplicate key
                raise
        
        try:
            self.cursor.execute("ALTER TABLE standard_invoice ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except mysql.connector.Error as e:
            if e.errno not in (1060, 1061):  # Column already exists or duplicate key
                raise
        
        try:
            self.cursor.execute("ALTER TABLE proforma_invoice ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except mysql.connector.Error as e:
            if e.errno not in (1060, 1061):  # Column already exists or duplicate key
                raise

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
            # Vérifier si le type a des produits utilisés dans des factures
            cursor.execute("""
                SELECT COUNT(*) FROM invoice_client ic 
                JOIN products p ON ic.product_id = p.id 
                WHERE p.product_type_id = %s
            """, (type_id,))
            count = cursor.fetchone()[0]
            if count > 0:
                raise ValueError("Cannot delete product type: it has products used in invoices.")
            
            # Supprimer les produits du type
            cursor.execute("DELETE FROM products WHERE product_type_id = %s", (type_id,))
            
            # Supprimer le type
            cursor.execute("DELETE FROM product_type WHERE id = %s", (type_id,))
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
    
    def save_standard_invoice(self, company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, selected_products):
        # Insérer la facture
        self.cursor.execute(
            "INSERT INTO standard_invoice (company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total)
        )
        invoice_id = self.cursor.lastrowid
        
        # Insérer les produits sélectionnés
        for product_id in selected_products:
            product = self.get_product_by_id(product_id)
            if product:
                item_total = float(product['subtotal'] or 0)
                self.cursor.execute(
                    "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (invoice_id, 'standard', product_id, product['physico'], product['micro'], product['toxico'], product['subtotal'], item_total)
                )
        
        self.conn.commit()
        return invoice_id

    def update_standard_invoice(self, invoice_id, company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, selected_products):
        self.cursor.execute(
            "UPDATE standard_invoice SET company_name=%s, stat=%s, nif=%s, address=%s, date_issue=%s, date_result=%s, product_ref=%s, resp=%s, total=%s WHERE id=%s",
            (company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, invoice_id)
        )

        # Mettre à jour les produits sélectionnés pour cette facture
        self.cursor.execute("DELETE FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'standard'))
        for product_id in selected_products:
            product = self.get_product_by_id(product_id)
            if product:
                item_total = float(product['subtotal'] or 0)
                self.cursor.execute(
                    "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (invoice_id, 'standard', product_id, product['physico'], product['micro'], product['toxico'], product['subtotal'], item_total)
                )
        self.conn.commit()
        return invoice_id

    def update_proforma_invoice(self, invoice_id, company_name, nif, stat, date, resp, total, selected_products):
        self.cursor.execute(
            "UPDATE proforma_invoice SET company_name=%s, nif=%s, stat=%s, date=%s, resp=%s, total=%s WHERE id=%s",
            (company_name, nif, stat, date, resp, total, invoice_id)
        )
        self.cursor.execute("DELETE FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'proforma'))
        for product_id in selected_products:
            product = self.get_product_by_id(product_id)
            if product:
                item_total = float(product['subtotal'] or 0)
                self.cursor.execute(
                    "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (invoice_id, 'proforma', product_id, product['physico'], product['micro'], product['toxico'], product['subtotal'], item_total)
                )
        self.conn.commit()
        return invoice_id

    def save_proforma_invoice(self, company_name, nif, stat, date, resp, total, selected_products):
        # Insérer la facture
        self.cursor.execute(
            "INSERT INTO proforma_invoice (company_name, nif, stat, date, resp, total) VALUES (%s, %s, %s, %s, %s, %s)",
            (company_name, nif, stat, date, resp, total)
        )
        invoice_id = self.cursor.lastrowid
        
        # Insérer les produits sélectionnés
        for product_id in selected_products:
            product = self.get_product_by_id(product_id)
            if product:
                item_total = float(product['subtotal'] or 0)
                self.cursor.execute(
                    "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (invoice_id, 'proforma', product_id, product['physico'], product['micro'], product['toxico'], product['subtotal'], item_total)
                )
        
        self.conn.commit()
        return invoice_id
    
    def get_product_by_id(self, product_id):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT product_name, ref_b_analyse, physico, micro, toxico, subtotal FROM products WHERE id=%s", (product_id,))
            return cursor.fetchone()
        finally:
            cursor.close()
    
    def get_standard_invoices(self):
        self.cursor.execute("SELECT id, company_name, address, date_issue, date_result, product_ref, resp, total FROM standard_invoice ORDER BY created_at ASC")
        results = self.cursor.fetchall()
        return [tuple(d.values()) for d in results]
    
    def get_proforma_invoices(self):
        self.cursor.execute("SELECT id, company_name, date, resp, total FROM proforma_invoice ORDER BY created_at ASC")
        results = self.cursor.fetchall()
        return [tuple(d.values()) for d in results]
    
    def get_invoice_items(self, invoice_id, invoice_type):
        self.cursor.execute("SELECT product_id FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, invoice_type))
        return [row['product_id'] for row in self.cursor.fetchall()]
    
    def get_standard_invoice_by_id(self, invoice_id):
        self.cursor.execute("SELECT * FROM standard_invoice WHERE id=%s", (invoice_id,))
        return self.cursor.fetchone()
    
    def get_proforma_invoice_by_id(self, invoice_id):
        self.cursor.execute("SELECT * FROM proforma_invoice WHERE id=%s", (invoice_id,))
        return self.cursor.fetchone()
    
    def delete_standard_invoice(self, invoice_id):
        # Supprimer les items associés
        self.cursor.execute("DELETE FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'standard'))
        # Supprimer la facture
        self.cursor.execute("DELETE FROM standard_invoice WHERE id=%s", (invoice_id,))
        self.conn.commit()
    
    def delete_proforma_invoice(self, invoice_id):
        # Supprimer les items associés
        self.cursor.execute("DELETE FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'proforma'))
        # Supprimer la facture
        self.cursor.execute("DELETE FROM proforma_invoice WHERE id=%s", (invoice_id,))
        self.conn.commit()

  