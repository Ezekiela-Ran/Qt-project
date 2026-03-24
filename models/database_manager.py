from models.database.tables import Tables
import mysql.connector

class DatabaseManager(Tables):
    table_name = ""

    @staticmethod
    def _normalize_num_act(value):
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _format_amount_for_display(value):
        try:
            amount = int(float(value or 0))
        except (TypeError, ValueError):
            amount = 0
        return f"{amount:,}".replace(",", " ") + " Ar"

    @classmethod
    def create_tables(cls):
        db = cls()
        try:
            db.proforma_invoice_table()
            db.standard_invoice_table()
            db.product_type_table()
            db.products_table()
            db.invoice_client_table()
            db.app_settings_table()
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

        try:
            self.cursor.execute("ALTER TABLE products MODIFY COLUMN num_act VARCHAR(255) NULL")
        except mysql.connector.Error as e:
            # Ignore harmless schema mismatch errors if already compatible.
            if e.errno not in (1060, 1061):
                raise

        try:
            self.cursor.execute("ALTER TABLE invoice_client ADD COLUMN ref_b_analyse INT NULL")
        except mysql.connector.Error as e:
            if e.errno not in (1060, 1061):
                raise

        try:
            self.cursor.execute("ALTER TABLE invoice_client ADD COLUMN num_act VARCHAR(255) NULL")
        except mysql.connector.Error as e:
            if e.errno not in (1060, 1061):
                raise

        try:
            self.cursor.execute("UPDATE products SET num_act = NULL WHERE num_act IS NOT NULL AND TRIM(num_act) IN ('', '0')")
            self.cursor.execute("CREATE UNIQUE INDEX uk_products_num_act ON products(num_act)")
        except mysql.connector.Error as e:
            if e.errno not in (1061, 1062):
                raise

    def fetch_all(self):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute(f"SELECT * FROM {self.table_name}")
            return cursor.fetchall()
        finally:
            cursor.close()

    def get_setting(self, key, default=None):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (key,))
            row = cursor.fetchone()
            return row[0] if row else default
        finally:
            cursor.close()

    def set_setting(self, key, value):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                """,
                (key, str(value)),
            )
            self.conn.commit()
        finally:
            cursor.close()

    def has_business_data(self):
        tables_to_check = (
            "standard_invoice",
            "proforma_invoice",
            "invoice_client",
            "products",
            "product_type",
        )
        cursor = self.conn.cursor()
        try:
            for table_name in tables_to_check:
                cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {table_name} LIMIT 1)")
                row = cursor.fetchone()
                if row and row[0]:
                    return True
            return False
        finally:
            cursor.close()

    def initialize_document_counters(self, invoice_start, ref_start):
        invoice_start = int(invoice_start)
        ref_start = int(ref_start)
        if invoice_start < 1 or ref_start < 1:
            raise ValueError("Les valeurs d'initialisation doivent être supérieures ou égales à 1.")
        if self.has_business_data():
            raise ValueError(
                "Initialisation impossible : des données existent déjà dans la base. Les compteurs ont déjà été initialisés et ne peuvent plus être modifiés."
            )

        self.cursor.execute(f"ALTER TABLE standard_invoice AUTO_INCREMENT = {invoice_start}")
        self.cursor.execute(f"ALTER TABLE proforma_invoice AUTO_INCREMENT = {invoice_start}")
        self.set_setting("ref_b_analyse_start", ref_start)
        self.set_setting("ref_b_analyse_last", ref_start - 1)
        self.set_setting("invoice_id_start", invoice_start)
        self.conn.commit()

    def get_max_ref_b_analyse(self):
        """Return the last allocated global ref_b_analyse (int) or configured start-1."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", ("ref_b_analyse_last",))
            row = cursor.fetchone()
            if row and row[0] is not None:
                try:
                    return int(row[0])
                except Exception:
                    pass
            configured_start = self.get_setting("ref_b_analyse_start", 1)
            try:
                return max(int(configured_start) - 1, 0)
            except Exception:
                return 0
        finally:
            cursor.close()

    def allocate_next_ref_b_analyse(self):
        """Atomically allocate and return the next global ref_b_analyse."""
        cursor = self.conn.cursor()
        try:
            start = self.get_setting("ref_b_analyse_start", 1)
            try:
                start_value = int(start)
            except Exception:
                start_value = 1
            cursor.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_value = setting_value
                """,
                ("ref_b_analyse_last", str(max(start_value - 1, 0))),
            )
            cursor.execute(
                """
                UPDATE app_settings
                SET setting_value = LAST_INSERT_ID(CAST(setting_value AS UNSIGNED) + 1)
                WHERE setting_key = %s
                """,
                ("ref_b_analyse_last",),
            )
            cursor.execute("SELECT LAST_INSERT_ID()")
            row = cursor.fetchone()
            next_ref = int(row[0]) if row and row[0] is not None else max(start_value, 1)
            self.conn.commit()
            return next_ref
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
    
    def add_product(self, type_id, product_name, ref="0", num_act=None, physico="0", toxico="0", micro="0", subtotal="0"):
        normalized_num_act = self._normalize_num_act(num_act)
        self.cursor.execute(
            "INSERT INTO products (product_type_id, product_name, ref_b_analyse, num_act, physico, toxico, micro, subtotal) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (type_id, product_name, ref, normalized_num_act, physico, toxico, micro, subtotal)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def delete_product(self, product_id):
        self.cursor.execute("DELETE FROM products WHERE id=%s", (product_id,))
        self.conn.commit()

    def is_num_act_unique(self, num_act, exclude_product_id=None):
        normalized_num_act = self._normalize_num_act(num_act)
        if normalized_num_act is None:
            return True

        cursor = self.conn.cursor()
        try:
            query = "SELECT COUNT(*) FROM products WHERE TRIM(num_act)=%s"
            params = [normalized_num_act]
            if exclude_product_id is not None:
                query += " AND id != %s"
                params.append(exclude_product_id)
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            return bool(row and row[0] == 0)
        finally:
            cursor.close()
    
    def update_product(self, product_id, ref, num_act, physico, toxico, micro, subtotal):
        # Backwards-compatible update: always update numeric fields; update ref only when provided.
        # num_act is now persisted per invoice line (invoice_client), not in products.
        try:
            self.cursor.execute(
                "UPDATE products SET physico=%s, toxico=%s, micro=%s, subtotal=%s WHERE id=%s",
                (physico, toxico, micro, subtotal, product_id)
            )
            # Update ref separately if needed
            if ref is not None:
                self.cursor.execute(
                    "UPDATE products SET ref_b_analyse=%s WHERE id=%s",
                    (ref, product_id)
                )
        finally:
            self.conn.commit()
        self.conn.commit()
    
    def save_standard_invoice(self, company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, selected_products, selected_refs=None, selected_num_acts=None):
        # Insérer la facture
        self.cursor.execute(
            "INSERT INTO standard_invoice (company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total)
        )
        invoice_id = self.cursor.lastrowid
        
        # Insérer les produits sélectionnés
        selected_refs = selected_refs or {}
        selected_num_acts = selected_num_acts or {}
        for product_id in selected_products:
            product = self.get_product_by_id(product_id)
            if product:
                item_total = float(product['subtotal'] or 0)
                ref_b_analyse = selected_refs.get(product_id)
                num_act = self._normalize_num_act(selected_num_acts.get(product_id))
                self.cursor.execute(
                    "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, ref_b_analyse, num_act, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (invoice_id, 'standard', product_id, ref_b_analyse, num_act, product['physico'], product['micro'], product['toxico'], product['subtotal'], item_total)
                )
        
        self.conn.commit()
        return invoice_id

    def update_standard_invoice(self, invoice_id, company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, selected_products, selected_refs=None, selected_num_acts=None):
        self.cursor.execute(
            "UPDATE standard_invoice SET company_name=%s, stat=%s, nif=%s, address=%s, date_issue=%s, date_result=%s, product_ref=%s, resp=%s, total=%s WHERE id=%s",
            (company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, invoice_id)
        )

        # Mettre à jour les produits sélectionnés pour cette facture
        self.cursor.execute("DELETE FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'standard'))
        selected_refs = selected_refs or {}
        selected_num_acts = selected_num_acts or {}
        for product_id in selected_products:
            product = self.get_product_by_id(product_id)
            if product:
                item_total = float(product['subtotal'] or 0)
                ref_b_analyse = selected_refs.get(product_id)
                num_act = self._normalize_num_act(selected_num_acts.get(product_id))
                self.cursor.execute(
                    "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, ref_b_analyse, num_act, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (invoice_id, 'standard', product_id, ref_b_analyse, num_act, product['physico'], product['micro'], product['toxico'], product['subtotal'], item_total)
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
                    "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, ref_b_analyse, num_act, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (invoice_id, 'proforma', product_id, None, None, product['physico'], product['micro'], product['toxico'], product['subtotal'], item_total)
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
                    "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, ref_b_analyse, num_act, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (invoice_id, 'proforma', product_id, None, None, product['physico'], product['micro'], product['toxico'], product['subtotal'], item_total)
                )
        
        self.conn.commit()
        return invoice_id
    
    def get_product_by_id(self, product_id):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT product_name, ref_b_analyse, num_act, physico, micro, toxico, subtotal FROM products WHERE id=%s", (product_id,))
            return cursor.fetchone()
        finally:
            cursor.close()
    
    def get_standard_invoices(self):
        self.cursor.execute("SELECT id, company_name, address, date_issue, date_result, product_ref, resp, total FROM standard_invoice ORDER BY created_at ASC")
        results = self.cursor.fetchall()
        for row in results:
            row['total'] = self._format_amount_for_display(row.get('total'))
        return [tuple(d.values()) for d in results]
    
    def get_proforma_invoices(self):
        self.cursor.execute("SELECT id, company_name, date, resp, total FROM proforma_invoice ORDER BY created_at ASC")
        results = self.cursor.fetchall()
        for row in results:
            row['total'] = self._format_amount_for_display(row.get('total'))
        return [tuple(d.values()) for d in results]
    
    def get_invoice_items(self, invoice_id, invoice_type):
        self.cursor.execute("SELECT product_id FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s ORDER BY id ASC", (invoice_id, invoice_type))
        return [row['product_id'] for row in self.cursor.fetchall()]

    def get_invoice_items_with_refs(self, invoice_id, invoice_type):
        self.cursor.execute(
            "SELECT product_id, ref_b_analyse, num_act FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s ORDER BY id ASC",
            (invoice_id, invoice_type),
        )
        return self.cursor.fetchall()
    
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

    def archive_and_reset(self, year=None):
        """Archive all non-archive tables into per-year archive tables,
        then truncate originals and reset AUTO_INCREMENT counters to 1.
        If `year` is None, use the current year as archive suffix.
        This routine does not change table schemas or application logic;
        it only copies rows into archive tables and clears the live tables.
        """
        import datetime
        if year is None:
            year = datetime.date.today().year
        suffix = str(year)
        try:
            # Find all user tables that are not already archive tables
            self.cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME NOT LIKE '%archive_%'"
            )
            tables = [row['TABLE_NAME'] for row in self.cursor.fetchall()]

            # Create archive tables and copy data (archive all tables)
            exclude_tables = {'products', 'product_type'}
            for tbl in tables:
                archive_name = f"{tbl}_archive_{suffix}"
                self.cursor.execute(f"CREATE TABLE IF NOT EXISTS {archive_name} LIKE {tbl}")
                self.cursor.execute(f"INSERT INTO {archive_name} SELECT * FROM {tbl}")
            self.conn.commit()

            # Truncate originals safely by disabling foreign key checks
            # Do NOT truncate product-related tables (we archived them but keep live data)
            self.cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            for tbl in tables:
                if tbl in exclude_tables:
                    continue
                self.cursor.execute(f"TRUNCATE TABLE {tbl}")
            self.cursor.execute("SET FOREIGN_KEY_CHECKS=1")

            # Reset AUTO_INCREMENT on tables that have it
            self.cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA=DATABASE() AND EXTRA LIKE '%auto_increment%'"
            )
            auto_tables = {row['TABLE_NAME'] for row in self.cursor.fetchall()}
            for tbl in auto_tables:
                try:
                    self.cursor.execute(f"ALTER TABLE {tbl} AUTO_INCREMENT=1")
                except Exception:
                    # ignore tables that can't be altered here
                    pass

            # Reset ref_b_analyse values in products to 0 so counter restarts at 1
            try:
                self.cursor.execute("UPDATE products SET ref_b_analyse=0")
            except Exception:
                pass

            try:
                self.cursor.execute("DELETE FROM app_settings WHERE setting_key IN ('ref_b_analyse_start', 'invoice_id_start')")
            except Exception:
                pass

            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

  