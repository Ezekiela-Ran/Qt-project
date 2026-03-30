from models.database.tables import Tables

class DatabaseManager(Tables):
    table_name = ""
    CURRENT_SCHEMA_VERSION = 3
    SCHEMA_VERSION_KEY = "schema_version"
    MYSQL_SCHEMA_LOCK_NAME = "fac_schema_bootstrap"
    MYSQL_SCHEMA_LOCK_TIMEOUT_SECONDS = 15
    MYSQL_COUNTER_INIT_LOCK_WAIT_SECONDS = 5

    @staticmethod
    def _normalize_num_act(value):
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _normalize_bool_flag(value):
        if value is None:
            return None
        return 1 if bool(value) else 0

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
            if db.is_mysql:
                db.ensure_mysql_schema_ready()
            else:
                db.bootstrap_schema()
        finally:
            db.close()

    def ensure_mysql_schema_ready(self):
        if not self._schema_requires_bootstrap():
            return

        if not self._acquire_mysql_schema_lock():
            if self._wait_for_mysql_schema_ready():
                return
            raise RuntimeError(
                "Initialisation du schema MySQL en cours sur un autre poste. "
                "Patientez quelques secondes puis relancez l'application."
            )

        try:
            if self._schema_requires_bootstrap():
                self.bootstrap_schema()
        finally:
            self._release_mysql_schema_lock()

    def bootstrap_schema(self):
        self.proforma_invoice_table()
        self.standard_invoice_table()
        self.product_type_table()
        self.products_table()
        self.invoice_client_table()
        self.certificate_entry_table()
        self.app_settings_table()
        self.users_table()
        self.migrate_tables()
        self.set_setting(self.SCHEMA_VERSION_KEY, self.CURRENT_SCHEMA_VERSION)

    def _schema_requires_bootstrap(self) -> bool:
        required_tables = {
            "proforma_invoice",
            "standard_invoice",
            "product_type",
            "products",
            "invoice_client",
            "certificate_entry",
            "app_settings",
            "users",
        }
        existing_tables = set(self.list_live_tables())
        if not required_tables.issubset(existing_tables):
            return True

        stored_version = self.get_setting(self.SCHEMA_VERSION_KEY)
        try:
            return int(stored_version or 0) < self.CURRENT_SCHEMA_VERSION
        except (TypeError, ValueError):
            return True

    def _acquire_mysql_schema_lock(self) -> bool:
        self.cursor.execute("SELECT GET_LOCK(%s, %s) AS lock_acquired", (
            self.MYSQL_SCHEMA_LOCK_NAME,
            self.MYSQL_SCHEMA_LOCK_TIMEOUT_SECONDS,
        ))
        row = self.cursor.fetchone()
        if not row:
            return False
        return bool(row.get("lock_acquired"))

    def _release_mysql_schema_lock(self):
        try:
            self.cursor.execute("SELECT RELEASE_LOCK(%s)", (self.MYSQL_SCHEMA_LOCK_NAME,))
            self.cursor.fetchone()
        except Exception:
            pass

    def _wait_for_mysql_schema_ready(self) -> bool:
        import time

        deadline = time.monotonic() + self.MYSQL_SCHEMA_LOCK_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if not self._schema_requires_bootstrap():
                return True
            time.sleep(1)
        return not self._schema_requires_bootstrap()

    def _ensure_column(self, table_name, column_name, definition):
        if not self.column_exists(table_name, column_name):
            self.cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def migrate_tables(self):
        # Migration pour ajouter les colonnes manquantes si elles n'existent pas
        self.certificate_entry_table()
        self._ensure_column("standard_invoice", "total", "DECIMAL(10,2) DEFAULT 0")
        self._ensure_column("proforma_invoice", "total", "DECIMAL(10,2) DEFAULT 0")
        self._ensure_column("standard_invoice", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        self._ensure_column("proforma_invoice", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        self._ensure_column("invoice_client", "ref_b_analyse", "INT NULL")
        self._ensure_column("invoice_client", "num_act", "VARCHAR(255) NULL")
        self._ensure_column("certificate_entry", "quantity", "VARCHAR(255) NULL")
        self._ensure_column("certificate_entry", "quantity_analysee", "VARCHAR(255) NULL")
        self._ensure_column("certificate_entry", "num_lot", "VARCHAR(255) NULL")
        self._ensure_column("certificate_entry", "num_act", "VARCHAR(255) NULL")
        self._ensure_column("certificate_entry", "num_cert", "VARCHAR(255) NULL")
        self._ensure_column("certificate_entry", "classe", "VARCHAR(255) NULL")
        self._ensure_column("certificate_entry", "date_production", "VARCHAR(32) NULL")
        self._ensure_column("certificate_entry", "date_production_modified", "INT NULL")
        self._ensure_column("certificate_entry", "date_peremption", "VARCHAR(32) NULL")
        self._ensure_column("certificate_entry", "date_peremption_modified", "INT NULL")
        self._ensure_column("certificate_entry", "num_prl", "VARCHAR(255) NULL")
        self._ensure_column("certificate_entry", "date_commerce", "VARCHAR(32) NULL")
        self._ensure_column("certificate_entry", "date_commerce_modified", "INT NULL")
        self._ensure_column("certificate_entry", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        self._ensure_column("users", "role", "VARCHAR(32) NOT NULL DEFAULT 'user'")
        self._ensure_column("users", "is_active", "INT NOT NULL DEFAULT 1")
        self._ensure_column("users", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        if self.is_mysql:
            try:
                self.cursor.execute("ALTER TABLE products MODIFY COLUMN num_act VARCHAR(191) NULL")
            except Exception:
                pass

            try:
                self.cursor.execute("ALTER TABLE users MODIFY COLUMN username VARCHAR(191) NOT NULL")
            except Exception:
                pass

        self.cursor.execute("UPDATE products SET num_act = NULL WHERE num_act IS NOT NULL AND TRIM(num_act) IN ('', '0')")
        self.cursor.execute("UPDATE users SET role = 'user' WHERE role IS NULL OR TRIM(role) = ''")
        self.cursor.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")

        if self.is_mysql:
            if not self.index_exists("uk_products_num_act"):
                self.cursor.execute("CREATE UNIQUE INDEX uk_products_num_act ON products(num_act)")
            if not self.index_exists("uk_certificate_entry_scope"):
                self.cursor.execute(
                    "CREATE UNIQUE INDEX uk_certificate_entry_scope ON certificate_entry(invoice_id, invoice_type, product_id, certificate_type)"
                )
            if not self.index_exists("uk_users_username"):
                self.cursor.execute("CREATE UNIQUE INDEX uk_users_username ON users(username)")
        else:
            self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_products_num_act ON products(num_act)")
            self.cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_certificate_entry_scope ON certificate_entry(invoice_id, invoice_type, product_id, certificate_type)"
            )
            self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_users_username ON users(username)")

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
                "UPDATE app_settings SET setting_value=%s WHERE setting_key=%s",
                (str(value), key),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s)",
                    (key, str(value)),
                )
            self.commit_if_needed()
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

    def has_invoice_history(self):
        tables_to_check = (
            "standard_invoice",
            "proforma_invoice",
            "invoice_client",
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

    def are_document_counters_initialized(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM app_settings WHERE setting_key IN (%s, %s)",
                ("invoice_id_start", "ref_b_analyse_start"),
            )
            row = cursor.fetchone()
            return bool(row and row[0] > 0)
        finally:
            cursor.close()

    def get_last_archive_reset_year(self):
        value = self.get_setting("last_archive_reset_year")
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def can_archive_and_reset(self, year=None):
        import datetime

        target_year = int(year or datetime.date.today().year)
        return self.get_last_archive_reset_year() != target_year

    def get_catalog_signature(self):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT COUNT(*) AS item_count, COALESCE(MAX(id), 0) AS max_id FROM product_type"
            )
            type_signature = cursor.fetchone() or {"item_count": 0, "max_id": 0}
            cursor.execute(
                "SELECT COUNT(*) AS item_count, COALESCE(MAX(id), 0) AS max_id FROM products"
            )
            product_signature = cursor.fetchone() or {"item_count": 0, "max_id": 0}
            return {
                "type_count": int(type_signature.get("item_count") or 0),
                "type_max_id": int(type_signature.get("max_id") or 0),
                "product_count": int(product_signature.get("item_count") or 0),
                "product_max_id": int(product_signature.get("max_id") or 0),
            }
        finally:
            cursor.close()

    def initialize_document_counters(self, invoice_start, ref_start):
        invoice_start = int(invoice_start)
        ref_start = int(ref_start)
        if invoice_start < 1 or ref_start < 1:
            raise ValueError("Les valeurs d'initialisation doivent être supérieures ou égales à 1.")
        if self.has_invoice_history():
            raise ValueError(
                "Initialisation impossible : des factures existent déjà dans la base. Les compteurs ne peuvent plus être modifiés."
            )

        with self.transaction():
            self.set_setting("ref_b_analyse_start", ref_start)
            self.set_setting("ref_b_analyse_last", ref_start - 1)
            self.set_setting("invoice_id_start", invoice_start)

    def _table_has_rows(self, table_name: str) -> bool:
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {table_name} LIMIT 1)")
            row = cursor.fetchone()
            return bool(row and row[0])
        finally:
            cursor.close()

    def _get_seed_invoice_id(self, table_name: str):
        if self._table_has_rows(table_name):
            return None

        configured_start = self.get_setting("invoice_id_start", 1)
        try:
            invoice_id = int(configured_start or 1)
        except (TypeError, ValueError):
            invoice_id = 1
        return max(invoice_id, 1)

    def _insert_invoice_header(self, table_name: str, payload: dict):
        seed_id = self._get_seed_invoice_id(table_name)
        columns = list(payload.keys())
        values = [payload[column] for column in columns]
        if seed_id is not None:
            columns = ["id", *columns]
            values = [seed_id, *values]

        placeholders = ", ".join(["%s"] * len(columns))
        column_clause = ", ".join(columns)
        self.cursor.execute(
            f"INSERT INTO {table_name} ({column_clause}) VALUES ({placeholders})",
            tuple(values),
        )
        if seed_id is not None:
            return seed_id
        return self.cursor.lastrowid

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
        """Allocate and return the next global ref_b_analyse."""
        start = self.get_setting("ref_b_analyse_start", 1)
        try:
            start_value = int(start)
        except Exception:
            start_value = 1

        if self.is_mysql:
            cursor = self.conn.cursor()
            try:
                with self.transaction():
                    cursor.execute(
                        "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s) "
                        "ON DUPLICATE KEY UPDATE setting_value = setting_value",
                        ("ref_b_analyse_last", str(start_value - 1)),
                    )
                    cursor.execute(
                        "UPDATE app_settings "
                        "SET setting_value = LAST_INSERT_ID(GREATEST(CAST(setting_value AS UNSIGNED), %s) + 1) "
                        "WHERE setting_key = %s",
                        (start_value - 1, "ref_b_analyse_last"),
                    )
                    cursor.execute("SELECT LAST_INSERT_ID()")
                    row = cursor.fetchone()
                    return int(row[0]) if row else start_value
            finally:
                cursor.close()

        with self.transaction():
            current = self.get_max_ref_b_analyse()
            next_ref = max(current + 1, start_value)
            self.set_setting("ref_b_analyse_last", next_ref)
            return next_ref

    def insert_type(self, name: str):
        cursor = self.conn.cursor()
        try:
            query = "INSERT INTO product_type (product_type_name) VALUES (%s)"
            cursor.execute(query, (name,))
            self.conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()

    def count_users(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            cursor.close()

    def count_admin_users(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM users WHERE role=%s", ("admin",))
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            cursor.close()

    def create_user(self, username, password_hash, role="user", is_active=True):
        normalized_username = str(username or "").strip()
        normalized_role = str(role or "user").strip().lower() or "user"
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, is_active) VALUES (%s, %s, %s, %s)",
                (normalized_username, password_hash, normalized_role, 1 if is_active else 0),
            )
            self.commit_if_needed()
            return cursor.lastrowid
        finally:
            cursor.close()

    def get_user_by_username(self, username, include_password_hash=True):
        cursor = self.conn.cursor(dictionary=True)
        try:
            fields = "id, username, password_hash, role, is_active, created_at" if include_password_hash else "id, username, role, is_active, created_at"
            cursor.execute(f"SELECT {fields} FROM users WHERE username=%s", (str(username or "").strip(),))
            return cursor.fetchone()
        finally:
            cursor.close()

    def get_user_by_id(self, user_id, include_password_hash=True):
        cursor = self.conn.cursor(dictionary=True)
        try:
            fields = "id, username, password_hash, role, is_active, created_at" if include_password_hash else "id, username, role, is_active, created_at"
            cursor.execute(f"SELECT {fields} FROM users WHERE id=%s", (user_id,))
            return cursor.fetchone()
        finally:
            cursor.close()

    def list_users(self):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id, username, role, is_active, created_at FROM users ORDER BY username ASC")
            return cursor.fetchall()
        finally:
            cursor.close()

    def update_user(self, user_id, username, role, is_active=True):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET username=%s, role=%s, is_active=%s WHERE id=%s",
                (str(username or "").strip(), str(role or "user").strip().lower() or "user", 1 if is_active else 0, user_id),
            )
            self.commit_if_needed()
        finally:
            cursor.close()

    def update_user_password(self, user_id, password_hash):
        cursor = self.conn.cursor()
        try:
            cursor.execute("UPDATE users SET password_hash=%s WHERE id=%s", (password_hash, user_id))
            self.commit_if_needed()
        finally:
            cursor.close()

    def delete_user(self, user_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
            self.commit_if_needed()
        finally:
            cursor.close()

    def update_type_name(self, type_id: int, name: str):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE product_type SET product_type_name=%s WHERE id=%s",
                (name, type_id),
            )
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

    def update_product_name(self, product_id, product_name):
        self.cursor.execute(
            "UPDATE products SET product_name=%s WHERE id=%s",
            (product_name, product_id),
        )
        self.conn.commit()

    def product_is_used_in_records(self, product_id):
        self.cursor.execute(
            "SELECT COUNT(*) AS cnt FROM invoice_client WHERE product_id=%s",
            (product_id,)
        )
        row = self.cursor.fetchone()
        return (row["cnt"] if row else 0) > 0

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
        with self.transaction():
            invoice_id = self._insert_invoice_header(
                "standard_invoice",
                {
                    "company_name": company_name,
                    "stat": stat,
                    "nif": nif,
                    "address": address,
                    "date_issue": date_issue,
                    "date_result": date_result,
                    "product_ref": product_ref,
                    "resp": resp,
                    "total": total,
                },
            )

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

            return invoice_id

    def update_standard_invoice(self, invoice_id, company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, selected_products, selected_refs=None, selected_num_acts=None):
        with self.transaction():
            self.cursor.execute(
                "UPDATE standard_invoice SET company_name=%s, stat=%s, nif=%s, address=%s, date_issue=%s, date_result=%s, product_ref=%s, resp=%s, total=%s WHERE id=%s",
                (company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, invoice_id)
            )

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
            return invoice_id

    def update_proforma_invoice(self, invoice_id, company_name, nif, stat, date, resp, total, selected_products):
        with self.transaction():
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
            return invoice_id

    def save_proforma_invoice(self, company_name, nif, stat, date, resp, total, selected_products):
        with self.transaction():
            invoice_id = self._insert_invoice_header(
                "proforma_invoice",
                {
                    "company_name": company_name,
                    "nif": nif,
                    "stat": stat,
                    "date": date,
                    "resp": resp,
                    "total": total,
                },
            )

            for product_id in selected_products:
                product = self.get_product_by_id(product_id)
                if product:
                    item_total = float(product['subtotal'] or 0)
                    self.cursor.execute(
                        "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, ref_b_analyse, num_act, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (invoice_id, 'proforma', product_id, None, None, product['physico'], product['micro'], product['toxico'], product['subtotal'], item_total)
                    )

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

    def get_certificate_entries(self, invoice_id, invoice_type, product_ids=None):
        cursor = self.conn.cursor(dictionary=True)
        try:
            query = (
                "SELECT invoice_id, invoice_type, product_id, certificate_type, quantity, quantity_analysee, "
                "num_lot, num_act, num_cert, classe, date_production, date_production_modified, "
                "date_peremption, date_peremption_modified, num_prl, date_commerce, date_commerce_modified "
                "FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s"
            )
            params = [invoice_id, invoice_type]
            if product_ids:
                placeholders = ", ".join(["%s"] * len(product_ids))
                query += f" AND product_id IN ({placeholders})"
                params.extend(product_ids)
            query += " ORDER BY product_id ASC, certificate_type ASC"
            cursor.execute(query, tuple(params))
            return cursor.fetchall()
        finally:
            cursor.close()

    def save_certificate_entry(self, invoice_id, invoice_type, product_id, certificate_type, payload):
        normalized_payload = {
            "quantity": str(payload.get("quantity") or "").strip(),
            "quantity_analysee": str(payload.get("quantity_analysee") or "").strip(),
            "num_lot": str(payload.get("num_lot") or "").strip(),
            "num_act": self._normalize_num_act(payload.get("num_act")),
            "num_cert": str(payload.get("num_cert") or "").strip(),
            "classe": str(payload.get("classe") or "").strip(),
            "date_production": str(payload.get("date_production") or "").strip(),
            "date_production_modified": self._normalize_bool_flag(payload.get("date_production_modified")),
            "date_peremption": str(payload.get("date_peremption") or "").strip(),
            "date_peremption_modified": self._normalize_bool_flag(payload.get("date_peremption_modified")),
            "num_prl": str(payload.get("num_prl") or "").strip(),
            "date_commerce": str(payload.get("date_commerce") or "").strip(),
            "date_commerce_modified": self._normalize_bool_flag(payload.get("date_commerce_modified")),
        }

        with self.transaction():
            self.cursor.execute(
                "SELECT id FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s AND product_id=%s AND certificate_type=%s",
                (invoice_id, invoice_type, product_id, certificate_type),
            )
            existing = self.cursor.fetchone()

            if existing:
                self.cursor.execute(
                    "UPDATE certificate_entry SET quantity=%s, quantity_analysee=%s, num_lot=%s, num_act=%s, "
                    "num_cert=%s, classe=%s, date_production=%s, date_production_modified=%s, "
                    "date_peremption=%s, date_peremption_modified=%s, num_prl=%s, date_commerce=%s, date_commerce_modified=%s "
                    "WHERE invoice_id=%s AND invoice_type=%s AND product_id=%s AND certificate_type=%s",
                    (
                        normalized_payload["quantity"],
                        normalized_payload["quantity_analysee"],
                        normalized_payload["num_lot"],
                        normalized_payload["num_act"],
                        normalized_payload["num_cert"],
                        normalized_payload["classe"],
                        normalized_payload["date_production"],
                        normalized_payload["date_production_modified"],
                        normalized_payload["date_peremption"],
                        normalized_payload["date_peremption_modified"],
                        normalized_payload["num_prl"],
                        normalized_payload["date_commerce"],
                        normalized_payload["date_commerce_modified"],
                        invoice_id,
                        invoice_type,
                        product_id,
                        certificate_type,
                    ),
                )
                return existing.get("id")

            self.cursor.execute(
                "INSERT INTO certificate_entry (invoice_id, invoice_type, product_id, certificate_type, quantity, quantity_analysee, "
                "num_lot, num_act, num_cert, classe, date_production, date_production_modified, date_peremption, "
                "date_peremption_modified, num_prl, date_commerce, date_commerce_modified) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    invoice_id,
                    invoice_type,
                    product_id,
                    certificate_type,
                    normalized_payload["quantity"],
                    normalized_payload["quantity_analysee"],
                    normalized_payload["num_lot"],
                    normalized_payload["num_act"],
                    normalized_payload["num_cert"],
                    normalized_payload["classe"],
                    normalized_payload["date_production"],
                    normalized_payload["date_production_modified"],
                    normalized_payload["date_peremption"],
                    normalized_payload["date_peremption_modified"],
                    normalized_payload["num_prl"],
                    normalized_payload["date_commerce"],
                    normalized_payload["date_commerce_modified"],
                ),
            )
            return self.cursor.lastrowid
    
    def get_standard_invoice_by_id(self, invoice_id):
        self.cursor.execute("SELECT * FROM standard_invoice WHERE id=%s", (invoice_id,))
        return self.cursor.fetchone()
    
    def get_proforma_invoice_by_id(self, invoice_id):
        self.cursor.execute("SELECT * FROM proforma_invoice WHERE id=%s", (invoice_id,))
        return self.cursor.fetchone()
    
    def delete_standard_invoice(self, invoice_id):
        with self.transaction():
            self.cursor.execute("DELETE FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'standard'))
            self.cursor.execute("DELETE FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'standard'))
            self.cursor.execute("DELETE FROM standard_invoice WHERE id=%s", (invoice_id,))
    
    def delete_proforma_invoice(self, invoice_id):
        with self.transaction():
            self.cursor.execute("DELETE FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'proforma'))
            self.cursor.execute("DELETE FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'proforma'))
            self.cursor.execute("DELETE FROM proforma_invoice WHERE id=%s", (invoice_id,))

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
        year = int(year)
        if not self.can_archive_and_reset(year):
            raise ValueError(
                f"La réinitialisation a déjà été effectuée pour l'année {year}."
            )

        suffix = str(year)
        with self.transaction():
            tables = self.list_live_tables()

            exclude_tables = {'products', 'product_type', 'users'}
            for tbl in tables:
                archive_name = f"{tbl}_archive_{suffix}"
                if self.is_mysql:
                    self.cursor.execute(f"CREATE TABLE IF NOT EXISTS {archive_name} LIKE {tbl}")
                    self.cursor.execute(f"INSERT IGNORE INTO {archive_name} SELECT * FROM {tbl}")
                else:
                    self.cursor.execute(f"CREATE TABLE IF NOT EXISTS {archive_name} AS SELECT * FROM {tbl} WHERE 0")
                    self.cursor.execute(f"INSERT INTO {archive_name} SELECT * FROM {tbl}")

            self.set_foreign_keys(False)
            try:
                for tbl in tables:
                    if tbl in exclude_tables:
                        continue
                    self.cursor.execute(f"DELETE FROM {tbl}")
                    self.reset_table_sequence(tbl, 1)
            finally:
                self.set_foreign_keys(True)

            if self.is_mysql:
                self.cursor.execute(
                    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA=DATABASE() AND EXTRA LIKE '%auto_increment%'"
                )
                auto_tables = {row['TABLE_NAME'] for row in self.cursor.fetchall()}
                for tbl in auto_tables:
                    try:
                        self.reset_table_sequence(tbl, 1)
                    except Exception:
                        pass

            try:
                self.cursor.execute("UPDATE products SET ref_b_analyse=0")
            except Exception:
                pass

            try:
                self.cursor.execute(
                    "DELETE FROM app_settings WHERE setting_key IN ('ref_b_analyse_start', 'ref_b_analyse_last', 'invoice_id_start')"
                )
            except Exception:
                pass

            self.set_setting("last_archive_reset_year", year)

  