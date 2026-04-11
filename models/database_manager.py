from datetime import datetime, timezone

from models.database.tables import Tables

class DatabaseManager(Tables):
    table_name = ""
    CURRENT_SCHEMA_VERSION = 7
    SCHEMA_VERSION_KEY = "schema_version"
    CATALOG_UPDATED_AT_KEY = "catalog_updated_at"
    CERTIFICATE_TYPES = ("CC", "CNC", "CP", "CNP", "CCON", "CNCON")
    CERTIFICATE_COUNTER_KEYS = {
        "CC": ("cert_cc_start", "cert_cc_last"),
        "CNC": ("cert_cnc_start", "cert_cnc_last"),
        "CP": ("cert_cp_start", "cert_cp_last"),
        "CNP": ("cert_cnp_start", "cert_cnp_last"),
        "CCON": ("cert_ccon_start", "cert_ccon_last"),
        "CNCON": ("cert_cncon_start", "cert_cncon_last"),
    }

    @classmethod
    def get_certificate_types(cls):
        return cls.CERTIFICATE_TYPES

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
    def _normalize_certificate_number(value):
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_amount_for_display(value):
        try:
            amount = int(float(value or 0))
        except (TypeError, ValueError):
            amount = 0
        return f"{amount:,}".replace(",", " ") + " Ar"

    @staticmethod
    def _catalog_timestamp_now():
        return datetime.now(timezone.utc).isoformat(timespec="microseconds")

    @classmethod
    def create_tables(cls):
        db = cls()
        try:
            db.bootstrap_schema()
        finally:
            db.close()

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


    def _ensure_column(self, table_name, column_name, definition):
        if not self.column_exists(table_name, column_name):
            self.cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def _ensure_certificate_entry_scope_index(self):
        if self.is_mysql:
            if self.index_exists("uk_certificate_entry_scope"):
                self.cursor.execute("DROP INDEX uk_certificate_entry_scope ON certificate_entry")
            self.cursor.execute(
                "CREATE UNIQUE INDEX uk_certificate_entry_scope ON certificate_entry(invoice_id, invoice_type, invoice_item_id, certificate_type)"
            )
            return

        self.cursor.execute("DROP INDEX IF EXISTS uk_certificate_entry_scope")
        self.cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uk_certificate_entry_scope ON certificate_entry(invoice_id, invoice_type, invoice_item_id, certificate_type)"
        )

    def _backfill_certificate_invoice_item_ids(self):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT id, invoice_id, invoice_type, product_id FROM certificate_entry WHERE invoice_item_id IS NULL ORDER BY id ASC"
            )
            entries = cursor.fetchall() or []
            for entry in entries:
                cursor.execute(
                    "SELECT id FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s AND product_id=%s ORDER BY id ASC LIMIT 1",
                    (entry["invoice_id"], entry["invoice_type"], entry["product_id"]),
                )
                invoice_item = cursor.fetchone()
                if not invoice_item:
                    continue
                self.cursor.execute(
                    "UPDATE certificate_entry SET invoice_item_id=%s WHERE id=%s",
                    (invoice_item["id"], entry["id"]),
                )
        finally:
            cursor.close()

    @staticmethod
    def _normalize_product_default_quantity(value):
        try:
            return max(int(value or 1), 1)
        except (TypeError, ValueError):
            return 1

    def _normalize_invoice_line_items(self, line_items, default_result_date=None):
        normalized_items = []
        for line in line_items or []:
            if isinstance(line, dict):
                product_id = line.get("product_id")
                ref_b_analyse = line.get("ref_b_analyse")
                num_act = self._normalize_num_act(line.get("num_act"))
                result_date = str(line.get("result_date") or default_result_date or "").strip() or None
            else:
                product_id = line
                ref_b_analyse = None
                num_act = None
                result_date = str(default_result_date or "").strip() or None
            if product_id is None:
                continue
            normalized_items.append(
                {
                    "product_id": int(product_id),
                    "ref_b_analyse": ref_b_analyse,
                    "num_act": num_act,
                    "result_date": result_date,
                }
            )
        return normalized_items

    def _insert_invoice_line_items(self, invoice_id, invoice_type, line_items, default_result_date=None):
        normalized_items = self._normalize_invoice_line_items(line_items, default_result_date=default_result_date)
        for line in normalized_items:
            product = self.get_product_by_id(line["product_id"])
            if not product:
                continue
            item_total = float(product["subtotal"] or 0)
            self.cursor.execute(
                "INSERT INTO invoice_client (invoice_id, invoice_type, product_id, ref_b_analyse, num_act, result_date, quantity, physico, micro, toxico, subtotal, total) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    invoice_id,
                    invoice_type,
                    line["product_id"],
                    line["ref_b_analyse"],
                    line["num_act"],
                    line["result_date"],
                    1,
                    product["physico"],
                    product["micro"],
                    product["toxico"],
                    product["subtotal"],
                    item_total,
                ),
            )
        if invoice_type == 'standard':
            self._sync_ref_b_analyse_last(normalized_items)

    def _sync_ref_b_analyse_last(self, line_items):
        ref_values = []
        for line in line_items or []:
            ref_value = line.get("ref_b_analyse") if isinstance(line, dict) else None
            if ref_value is None:
                continue
            try:
                ref_values.append(int(ref_value))
            except (TypeError, ValueError):
                continue

        if not ref_values:
            return

        highest_allocated_ref = max(ref_values)
        current_last = self.get_max_ref_b_analyse()
        if highest_allocated_ref > current_last:
            self.set_setting("ref_b_analyse_last", highest_allocated_ref)

    def migrate_tables(self):
        # Migration pour ajouter les colonnes manquantes si elles n'existent pas
        self.certificate_entry_table()
        self._ensure_column("standard_invoice", "total", "DECIMAL(10,2) DEFAULT 0")
        self._ensure_column("proforma_invoice", "total", "DECIMAL(10,2) DEFAULT 0")
        self._ensure_column("standard_invoice", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        self._ensure_column("proforma_invoice", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        self._ensure_column("products", "default_quantity", "INT NOT NULL DEFAULT 1")
        self._ensure_column("products", "analysis_duration_days", "INT NOT NULL DEFAULT 0")
        self._ensure_column("invoice_client", "ref_b_analyse", "INT NULL")
        self._ensure_column("invoice_client", "num_act", "VARCHAR(255) NULL")
        self._ensure_column("invoice_client", "result_date", "VARCHAR(32) NULL")
        self._ensure_column("invoice_client", "quantity", "INT NOT NULL DEFAULT 1")
        self._ensure_column("certificate_entry", "invoice_item_id", "INT NULL")
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
        self._ensure_column("certificate_entry", "date_cert", "VARCHAR(32) NULL")
        self._ensure_column("certificate_entry", "date_cert_modified", "INT NULL")
        self._ensure_column("certificate_entry", "printed_at", "VARCHAR(32) NULL")
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
        self.cursor.execute("UPDATE products SET default_quantity = 1 WHERE default_quantity IS NULL OR default_quantity < 1")
        self.cursor.execute("UPDATE users SET role = 'user' WHERE role IS NULL OR TRIM(role) = ''")
        self.cursor.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")

        self._ensure_certificate_counter_settings()
        self._backfill_certificate_invoice_item_ids()
        self._migrate_certificate_entry_type_storage()

        if self.is_mysql:
            if not self.index_exists("uk_products_num_act"):
                self.cursor.execute("CREATE UNIQUE INDEX uk_products_num_act ON products(num_act)")
            self._ensure_certificate_entry_scope_index()
            if not self.index_exists("uk_users_username"):
                self.cursor.execute("CREATE UNIQUE INDEX uk_users_username ON users(username)")
        else:
            self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_products_num_act ON products(num_act)")
            self._ensure_certificate_entry_scope_index()
            self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_users_username ON users(username)")

    def _ensure_certificate_counter_settings(self):
        for start_key, last_key in self.CERTIFICATE_COUNTER_KEYS.values():
            start_value = self.get_setting(start_key)
            if start_value in (None, ""):
                self.set_setting(start_key, 1)
                start_value = 1
            try:
                normalized_start = max(int(start_value), 1)
            except (TypeError, ValueError):
                normalized_start = 1
                self.set_setting(start_key, normalized_start)

            last_value = self.get_setting(last_key)
            if last_value in (None, ""):
                self.set_setting(last_key, normalized_start - 1)

    def _migrate_certificate_entry_type_storage(self):
        if self.is_mysql:
            self._migrate_mysql_certificate_types()
            return
        self._migrate_sqlite_certificate_types()

    def _migrate_mysql_certificate_types(self):
        enum_values = ", ".join(f"'{cert_type}'" for cert_type in self.CERTIFICATE_TYPES)
        try:
            self.cursor.execute(
                f"ALTER TABLE certificate_entry MODIFY COLUMN certificate_type ENUM({enum_values}) NOT NULL"
            )
        except Exception:
            return

    def _migrate_sqlite_certificate_types(self):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='certificate_entry'"
            )
            row = cursor.fetchone()
            create_sql = str(row[0] or "") if row else ""
            if all(cert_type in create_sql for cert_type in self.CERTIFICATE_TYPES):
                return

            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS certificate_entry__new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL,
                    invoice_type TEXT NOT NULL CHECK (invoice_type IN ('standard', 'proforma')),
                    product_id INTEGER NOT NULL,
                    invoice_item_id INTEGER NULL,
                    certificate_type TEXT NOT NULL CHECK (certificate_type IN ('CC', 'CNC', 'CP', 'CNP', 'CCON', 'CNCON')),
                    quantity TEXT,
                    quantity_analysee TEXT,
                    num_lot TEXT,
                    num_act TEXT,
                    num_cert TEXT,
                    classe TEXT,
                    date_production TEXT,
                    printed_at TEXT NULL,
                    date_production_modified INTEGER,
                    date_peremption TEXT,
                    date_peremption_modified INTEGER,
                    num_prl TEXT,
                    date_commerce TEXT,
                    date_commerce_modified INTEGER,
                    date_cert TEXT,
                    date_cert_modified INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO certificate_entry__new (
                    id, invoice_id, invoice_type, product_id, invoice_item_id, certificate_type, quantity,
                    quantity_analysee, num_lot, num_act, num_cert, classe, date_production, printed_at,
                    date_production_modified, date_peremption, date_peremption_modified, num_prl,
                    date_commerce, date_commerce_modified, date_cert, date_cert_modified, created_at
                )
                SELECT
                    id, invoice_id, invoice_type, product_id, invoice_item_id, certificate_type, quantity,
                    quantity_analysee, num_lot, num_act, num_cert, classe, date_production, printed_at,
                    date_production_modified, date_peremption, date_peremption_modified, num_prl,
                    date_commerce, date_commerce_modified, date_cert, date_cert_modified, created_at
                FROM certificate_entry
                """
            )
            cursor.execute("DROP TABLE certificate_entry")
            cursor.execute("ALTER TABLE certificate_entry__new RENAME TO certificate_entry")
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uk_certificate_entry_scope ON certificate_entry(invoice_id, invoice_type, invoice_item_id, certificate_type)"
            )
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()

    def fetch_all(self):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute(f"SELECT * FROM {self.table_name}")
            return cursor.fetchall()
        finally:
            cursor.close()

    def get_all_product_types(self):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT * FROM product_type ORDER BY product_type_name ASC, id ASC"
            )
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
            required_keys = ["invoice_id_start", "ref_b_analyse_start", *[keys[0] for keys in self.CERTIFICATE_COUNTER_KEYS.values()]]
            placeholders = ", ".join(["%s"] * len(required_keys))
            cursor.execute(
                f"SELECT COUNT(*) FROM app_settings WHERE setting_key IN ({placeholders})",
                tuple(required_keys),
            )
            row = cursor.fetchone()
            return bool(row and row[0] == len(required_keys))
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
            catalog_updated_at = self.get_setting(self.CATALOG_UPDATED_AT_KEY)
            cursor.execute(
                "SELECT COUNT(*) AS item_count, COALESCE(MAX(id), 0) AS max_id FROM product_type"
            )
            type_signature = cursor.fetchone() or {"item_count": 0, "max_id": 0}
            cursor.execute(
                "SELECT COUNT(*) AS item_count, COALESCE(MAX(id), 0) AS max_id FROM products"
            )
            product_signature = cursor.fetchone() or {"item_count": 0, "max_id": 0}
            return {
                "catalog_updated_at": str(catalog_updated_at or ""),
                "type_count": int(type_signature.get("item_count") or 0),
                "type_max_id": int(type_signature.get("max_id") or 0),
                "product_count": int(product_signature.get("item_count") or 0),
                "product_max_id": int(product_signature.get("max_id") or 0),
            }
        finally:
            cursor.close()

    def touch_catalog(self):
        self.set_setting(self.CATALOG_UPDATED_AT_KEY, self._catalog_timestamp_now())

    def initialize_document_counters(
        self,
        invoice_start,
        ref_start,
        cert_cc_start,
        cert_cnc_start,
        cert_cp_start=1,
        cert_cnp_start=1,
        cert_ccon_start=1,
        cert_cncon_start=1,
    ):
        invoice_start = int(invoice_start)
        ref_start = int(ref_start)
        certificate_starts = {
            "CC": int(cert_cc_start),
            "CNC": int(cert_cnc_start),
            "CP": int(cert_cp_start),
            "CNP": int(cert_cnp_start),
            "CCON": int(cert_ccon_start),
            "CNCON": int(cert_cncon_start),
        }
        if invoice_start < 1 or ref_start < 1 or any(value < 1 for value in certificate_starts.values()):
            raise ValueError("Les valeurs d'initialisation doivent être supérieures ou égales à 1.")
        if self.has_invoice_history():
            raise ValueError(
                "Initialisation impossible : des factures existent déjà dans la base. Les compteurs ne peuvent plus être modifiés."
            )

        with self.transaction():
            self.set_setting("ref_b_analyse_start", ref_start)
            self.set_setting("ref_b_analyse_last", ref_start - 1)
            self.set_setting("invoice_id_start", invoice_start)
            for cert_type, start_value in certificate_starts.items():
                start_key, last_key = self._get_certificate_counter_keys(cert_type)
                self.set_setting(start_key, start_value)
                self.set_setting(last_key, start_value - 1)

    @classmethod
    def _get_certificate_counter_keys(cls, cert_type: str):
        normalized_type = str(cert_type or "").strip().upper()
        if normalized_type not in cls.CERTIFICATE_COUNTER_KEYS:
            raise ValueError(f"Type de certificat invalide : {cert_type}")
        return cls.CERTIFICATE_COUNTER_KEYS[normalized_type]

    def _get_existing_max_cert_number(self, cert_type: str) -> int:
        normalized_type = str(cert_type or "").strip().upper()
        cursor = self.conn.cursor()
        try:
            cast_expr = "CAST(num_cert AS UNSIGNED)" if self.is_mysql else "CAST(num_cert AS INTEGER)"
            cursor.execute(
                f"SELECT COALESCE(MAX({cast_expr}), 0) FROM certificate_entry "
                "WHERE certificate_type=%s AND TRIM(COALESCE(num_cert, '')) <> ''",
                (normalized_type,),
            )
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except Exception:
            return 0
        finally:
            cursor.close()

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
    def _normalize_certificate_payload(self, payload):
        return {
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
            "date_cert": str(payload.get("date_cert") or "").strip(),
            "date_cert_modified": self._normalize_bool_flag(payload.get("date_cert_modified")),
        }
    def _get_certificate_entry(self, invoice_id, invoice_type, product_id, certificate_type, invoice_item_id=None):
        cursor = self.conn.cursor(dictionary=True)
        try:
            if invoice_item_id is not None:
                cursor.execute(
                    "SELECT * FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s AND invoice_item_id=%s AND certificate_type=%s",
                    (invoice_id, invoice_type, invoice_item_id, certificate_type),
                )
            else:
                cursor.execute(
                    "SELECT * FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s AND product_id=%s AND certificate_type=%s ORDER BY id ASC LIMIT 1",
                    (invoice_id, invoice_type, product_id, certificate_type),
                )
            return cursor.fetchone()
        finally:
            cursor.close()

    def _sync_certificate_counter(self, cert_type: str):
        start_key, last_key = self._get_certificate_counter_keys(cert_type)
        existing_max = self._get_existing_max_cert_number(cert_type)
        if existing_max > 0:
            self.set_setting(last_key, existing_max)
            return existing_max

        configured_start = self.get_setting(start_key, 1)
        try:
            next_last = max(int(configured_start) - 1, 0)
        except (TypeError, ValueError):
            next_last = 0
        self.set_setting(last_key, next_last)
        return next_last

    def _resequence_certificate_type_after_removal(self, cert_type: str, removed_number: int | None):
        if removed_number is None:
            self._sync_certificate_counter(cert_type)
            return

        cursor = self.conn.cursor(dictionary=True)
        try:
            cast_expr = "CAST(num_cert AS UNSIGNED)" if self.is_mysql else "CAST(num_cert AS INTEGER)"
            cursor.execute(
                f"SELECT id, num_cert FROM certificate_entry WHERE certificate_type=%s "
                "AND TRIM(COALESCE(num_cert, '')) <> '' "
                f"ORDER BY {cast_expr} ASC, id ASC",
                (cert_type,),
            )
            rows = cursor.fetchall() or []
            for entry in rows:
                current_number = self._normalize_certificate_number(entry.get("num_cert"))
                if current_number is None or current_number <= removed_number:
                    continue
                self.cursor.execute(
                    "UPDATE certificate_entry SET num_cert=%s WHERE id=%s",
                    (str(current_number - 1), entry.get("id")),
                )
        finally:
            cursor.close()

        self._sync_certificate_counter(cert_type)

    def switch_certificate_entry_type(self, invoice_id, invoice_type, product_id, source_type, target_type, payload, invoice_item_id=None):
        normalized_source = str(source_type or "").strip().upper()
        normalized_target = str(target_type or "").strip().upper()
        if normalized_source == normalized_target:
            raise ValueError("Le type source et le type cible doivent etre differents.")

        self._get_certificate_counter_keys(normalized_source)
        self._get_certificate_counter_keys(normalized_target)

        normalized_payload = self._normalize_certificate_payload(payload)
        with self.transaction():
            source_entry = self._get_certificate_entry(invoice_id, invoice_type, product_id, normalized_source, invoice_item_id=invoice_item_id)
            target_entry = self._get_certificate_entry(invoice_id, invoice_type, product_id, normalized_target, invoice_item_id=invoice_item_id)

            source_number = self._normalize_certificate_number(
                normalized_payload.get("num_cert") or (source_entry or {}).get("num_cert")
            )
            target_number = self._normalize_certificate_number((target_entry or {}).get("num_cert"))

            if source_entry:
                self.cursor.execute(
                    "DELETE FROM certificate_entry WHERE id=%s",
                    (source_entry.get("id"),),
                )
            if source_number is not None:
                self._resequence_certificate_type_after_removal(normalized_source, source_number)
            else:
                self._sync_certificate_counter(normalized_source)

            if target_entry:
                self.cursor.execute(
                    "DELETE FROM certificate_entry WHERE id=%s",
                    (target_entry.get("id"),),
                )
                self._resequence_certificate_type_after_removal(normalized_target, target_number)

            normalized_payload["num_cert"] = ""
            if source_number is not None:
                normalized_payload["num_cert"] = str(self.allocate_next_cert_number(normalized_target))

            self.save_certificate_entry(
                invoice_id,
                invoice_type,
                product_id,
                normalized_target,
                normalized_payload,
                invoice_item_id=invoice_item_id,
            )
            return normalized_payload.copy()

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

    def get_max_cert_number(self, cert_type: str):
        """Return the last allocated certificate number for the given type."""
        start_key, last_key = self._get_certificate_counter_keys(cert_type)
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (last_key,))
            row = cursor.fetchone()
            if row and row[0] is not None:
                try:
                    return int(row[0])
                except Exception:
                    pass

            existing_max = self._get_existing_max_cert_number(cert_type)
            if existing_max > 0:
                return existing_max

            configured_start = self.get_setting(start_key, 1)
            try:
                return max(int(configured_start) - 1, 0)
            except Exception:
                return 0
        finally:
            cursor.close()

    def allocate_next_cert_number(self, cert_type: str):
        """Allocate and return the next certificate number for the given type."""
        start_key, last_key = self._get_certificate_counter_keys(cert_type)
        start = self.get_setting(start_key, 1)
        try:
            start_value = int(start)
        except Exception:
            start_value = 1

        with self.transaction():
            current = self.get_max_cert_number(cert_type)
            next_value = max(current + 1, start_value)
            self.set_setting(last_key, next_value)
            return next_value

    def insert_type(self, name: str):
        cursor = self.conn.cursor()
        try:
            query = "INSERT INTO product_type (product_type_name) VALUES (%s)"
            cursor.execute(query, (name,))
            self.conn.commit()
            self.touch_catalog()
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
            self.touch_catalog()
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
            self.touch_catalog()
        finally:
            cursor.close()

    def get_products_by_type(self, type_id):
        self.cursor.execute(
            "SELECT id, product_name, default_quantity, analysis_duration_days, ref_b_analyse, num_act, physico, toxico, micro, subtotal "
            "FROM products WHERE product_type_id=%s ORDER BY product_name ASC, id ASC",
            (type_id,),
        )
        return self.cursor.fetchall()
    
    def add_product(self, type_id, product_name, analysis_duration_days=0, default_quantity=1, ref="0", num_act=None, physico="0", toxico="0", micro="0", subtotal="0"):
        normalized_num_act = self._normalize_num_act(num_act)
        quantity_value = self._normalize_product_default_quantity(default_quantity)
        try:
            duration_value = max(int(analysis_duration_days or 0), 0)
        except (TypeError, ValueError):
            duration_value = 0
        self.cursor.execute(
            "INSERT INTO products (product_type_id, product_name, default_quantity, analysis_duration_days, ref_b_analyse, num_act, physico, toxico, micro, subtotal) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (type_id, product_name, quantity_value, duration_value, ref, normalized_num_act, physico, toxico, micro, subtotal)
        )
        self.conn.commit()
        self.touch_catalog()
        return self.cursor.lastrowid

    def update_product_name(self, product_id, product_name):
        self.cursor.execute(
            "UPDATE products SET product_name=%s WHERE id=%s",
            (product_name, product_id),
        )
        self.conn.commit()
        self.touch_catalog()

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
        self.touch_catalog()

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
    
    def update_product(self, product_id, ref, num_act, physico, toxico, micro, subtotal, analysis_duration_days=None, default_quantity=None):
        try:
            self.cursor.execute(
                "UPDATE products SET physico=%s, toxico=%s, micro=%s, subtotal=%s WHERE id=%s",
                (physico, toxico, micro, subtotal, product_id)
            )
            if ref is not None:
                self.cursor.execute(
                    "UPDATE products SET ref_b_analyse=%s WHERE id=%s",
                    (ref, product_id)
                )
            if analysis_duration_days is not None:
                try:
                    duration_value = max(int(analysis_duration_days or 0), 0)
                except (TypeError, ValueError):
                    duration_value = 0
                self.cursor.execute(
                    "UPDATE products SET analysis_duration_days=%s WHERE id=%s",
                    (duration_value, product_id)
                )
            if default_quantity is not None:
                self.cursor.execute(
                    "UPDATE products SET default_quantity=%s WHERE id=%s",
                    (self._normalize_product_default_quantity(default_quantity), product_id)
                )
        finally:
            self.conn.commit()
        self.touch_catalog()
    
    def save_standard_invoice(self, company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, selected_line_items):
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

            self._insert_invoice_line_items(invoice_id, 'standard', selected_line_items, default_result_date=date_result)

            return invoice_id

    def update_standard_invoice(self, invoice_id, company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, selected_line_items):
        with self.transaction():
            self.cursor.execute(
                "UPDATE standard_invoice SET company_name=%s, stat=%s, nif=%s, address=%s, date_issue=%s, date_result=%s, product_ref=%s, resp=%s, total=%s WHERE id=%s",
                (company_name, stat, nif, address, date_issue, date_result, product_ref, resp, total, invoice_id)
            )

            self.cursor.execute("DELETE FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'standard'))
            self._insert_invoice_line_items(invoice_id, 'standard', selected_line_items, default_result_date=date_result)
            return invoice_id

    def update_proforma_invoice(self, invoice_id, company_name, nif, stat, date, resp, total, selected_line_items):
        with self.transaction():
            self.cursor.execute(
                "UPDATE proforma_invoice SET company_name=%s, nif=%s, stat=%s, date=%s, resp=%s, total=%s WHERE id=%s",
                (company_name, nif, stat, date, resp, total, invoice_id)
            )
            self.cursor.execute("DELETE FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s", (invoice_id, 'proforma'))
            self._insert_invoice_line_items(invoice_id, 'proforma', selected_line_items, default_result_date=None)
            return invoice_id

    def save_proforma_invoice(self, company_name, nif, stat, date, resp, total, selected_line_items):
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

            self._insert_invoice_line_items(invoice_id, 'proforma', selected_line_items, default_result_date=None)

            return invoice_id
    
    def get_product_by_id(self, product_id):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT product_name, default_quantity, analysis_duration_days, ref_b_analyse, num_act, physico, micro, toxico, subtotal FROM products WHERE id=%s", (product_id,))
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
            "SELECT id AS invoice_item_id, product_id, ref_b_analyse, num_act, result_date FROM invoice_client WHERE invoice_id=%s AND invoice_type=%s ORDER BY id ASC",
            (invoice_id, invoice_type),
        )
        return self.cursor.fetchall()

    def get_certificate_entries(self, invoice_id, invoice_type, product_ids=None, invoice_item_ids=None):
        cursor = self.conn.cursor(dictionary=True)
        try:
            query = (
                "SELECT invoice_id, invoice_type, product_id, invoice_item_id, certificate_type, quantity, quantity_analysee, "
                "num_lot, num_act, num_cert, classe, date_production, date_production_modified, "
                "date_peremption, date_peremption_modified, num_prl, date_commerce, date_commerce_modified, "
                "date_cert, date_cert_modified, printed_at "
                "FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s"
            )
            params = [invoice_id, invoice_type]
            if invoice_item_ids:
                placeholders = ", ".join(["%s"] * len(invoice_item_ids))
                query += f" AND invoice_item_id IN ({placeholders})"
                params.extend(invoice_item_ids)
            if product_ids:
                placeholders = ", ".join(["%s"] * len(product_ids))
                query += f" AND product_id IN ({placeholders})"
                params.extend(product_ids)
            query += " ORDER BY COALESCE(invoice_item_id, 0) ASC, product_id ASC, certificate_type ASC"
            cursor.execute(query, tuple(params))
            return cursor.fetchall()
        finally:
            cursor.close()

    def get_all_standard_certificate_entries(self):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT invoice_id, invoice_type, product_id, invoice_item_id, certificate_type, quantity, quantity_analysee, "
                "num_lot, num_act, num_cert, classe, date_production, date_production_modified, "
                "date_peremption, date_peremption_modified, num_prl, date_commerce, date_commerce_modified, "
                "date_cert, date_cert_modified, printed_at "
                "FROM certificate_entry WHERE invoice_type=%s ORDER BY invoice_id ASC, COALESCE(invoice_item_id, 0) ASC, product_id ASC, certificate_type ASC",
                ("standard",),
            )
            return cursor.fetchall()
        finally:
            cursor.close()

    @staticmethod
    def _certificate_entry_scope_key(entry):
        invoice_item_id = entry.get("invoice_item_id")
        if invoice_item_id is not None:
            return ("item", int(invoice_item_id))
        return ("legacy", entry.get("invoice_id"), entry.get("invoice_type"), entry.get("product_id"))

    def save_certificate_entry(self, invoice_id, invoice_type, product_id, certificate_type, payload, invoice_item_id=None):
        normalized_payload = self._normalize_certificate_payload(payload)

        with self.transaction():
            if invoice_item_id is not None:
                self.cursor.execute(
                    "SELECT id FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s AND invoice_item_id=%s AND certificate_type=%s",
                    (invoice_id, invoice_type, invoice_item_id, certificate_type),
                )
            else:
                self.cursor.execute(
                    "SELECT id FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s AND product_id=%s AND certificate_type=%s ORDER BY id ASC LIMIT 1",
                    (invoice_id, invoice_type, product_id, certificate_type),
                )
            existing = self.cursor.fetchone()

            if existing:
                if invoice_item_id is not None:
                    self.cursor.execute(
                        "UPDATE certificate_entry SET quantity=%s, quantity_analysee=%s, num_lot=%s, num_act=%s, "
                        "num_cert=%s, classe=%s, date_production=%s, date_production_modified=%s, "
                        "date_peremption=%s, date_peremption_modified=%s, num_prl=%s, date_commerce=%s, date_commerce_modified=%s, "
                        "date_cert=%s, date_cert_modified=%s, printed_at=%s "
                        "WHERE invoice_id=%s AND invoice_type=%s AND invoice_item_id=%s AND certificate_type=%s",
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
                            normalized_payload["date_cert"],
                            normalized_payload["date_cert_modified"],
                            str(payload.get("printed_at") or "").strip() or None,
                            invoice_id,
                            invoice_type,
                            invoice_item_id,
                            certificate_type,
                        ),
                    )
                else:
                    self.cursor.execute(
                        "UPDATE certificate_entry SET quantity=%s, quantity_analysee=%s, num_lot=%s, num_act=%s, "
                        "num_cert=%s, classe=%s, date_production=%s, date_production_modified=%s, "
                        "date_peremption=%s, date_peremption_modified=%s, num_prl=%s, date_commerce=%s, date_commerce_modified=%s, "
                        "date_cert=%s, date_cert_modified=%s, printed_at=%s "
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
                            normalized_payload["date_cert"],
                            normalized_payload["date_cert_modified"],
                            str(payload.get("printed_at") or "").strip() or None,
                            invoice_id,
                            invoice_type,
                            product_id,
                            certificate_type,
                        ),
                    )
                return existing.get("id")

            self.cursor.execute(
                "INSERT INTO certificate_entry (invoice_id, invoice_type, product_id, invoice_item_id, certificate_type, quantity, quantity_analysee, "
                "num_lot, num_act, num_cert, classe, date_production, date_production_modified, date_peremption, "
                "date_peremption_modified, num_prl, date_commerce, date_commerce_modified, date_cert, date_cert_modified, printed_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    invoice_id,
                    invoice_type,
                    product_id,
                    invoice_item_id,
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
                    normalized_payload["date_cert"],
                    normalized_payload["date_cert_modified"],
                    str(payload.get("printed_at") or "").strip() or None,
                ),
            )
            return self.cursor.lastrowid

    def mark_certificate_entry_printed(self, invoice_id, invoice_type, product_id, certificate_type, printed_at, invoice_item_id=None):
        with self.transaction():
            if invoice_item_id is not None:
                self.cursor.execute(
                    "UPDATE certificate_entry SET printed_at=%s WHERE invoice_id=%s AND invoice_type=%s AND invoice_item_id=%s AND certificate_type=%s",
                    (printed_at, invoice_id, invoice_type, invoice_item_id, certificate_type),
                )
            else:
                self.cursor.execute(
                    "UPDATE certificate_entry SET printed_at=%s WHERE invoice_id=%s AND invoice_type=%s AND product_id=%s AND certificate_type=%s",
                    (printed_at, invoice_id, invoice_type, product_id, certificate_type),
                )

    def get_certificate_work_queue(self, include_printed=False):
        cursor = self.conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT ic.id AS invoice_item_id, ic.invoice_id, ic.invoice_type, ic.product_id, ic.result_date, ic.ref_b_analyse, ic.num_act AS line_num_act, "
                "si.company_name, si.address, si.stat, si.nif, si.date_issue, si.date_result AS invoice_date_result, si.product_ref, si.resp, "
                "p.product_name "
                "FROM invoice_client ic "
                "INNER JOIN standard_invoice si ON si.id = ic.invoice_id AND ic.invoice_type = 'standard' "
                "INNER JOIN products p ON p.id = ic.product_id "
                "ORDER BY CASE WHEN TRIM(COALESCE(ic.result_date, '')) = '' THEN 1 ELSE 0 END ASC, ic.result_date ASC, si.id ASC, p.product_name ASC, ic.id ASC"
            )
            rows = cursor.fetchall() or []
            entry_rows = self.get_all_standard_certificate_entries()
            entries_by_scope = {}
            for entry in entry_rows:
                entries_by_scope.setdefault(self._certificate_entry_scope_key(entry), {})[entry.get("certificate_type")] = entry
            queue = []
            for row in rows:
                scoped_entries = entries_by_scope.get(self._certificate_entry_scope_key(row), {})
                active_certificate_type = None
                active_num_cert = ""
                printed_at = None
                for cert_type in self.get_certificate_types():
                    entry = scoped_entries.get(cert_type)
                    if not entry:
                        continue
                    if str(entry.get("num_cert") or "").strip() or entry.get("printed_at"):
                        active_certificate_type = cert_type
                        active_num_cert = str(entry.get("num_cert") or "").strip()
                        printed_at = entry.get("printed_at")
                        break

                row["active_certificate_type"] = active_certificate_type
                row["active_num_cert"] = active_num_cert
                row["printed_at"] = printed_at

                if include_printed and not printed_at:
                    continue
                if not include_printed and printed_at:
                    continue
                queue.append(row)
            return queue
        finally:
            cursor.close()

    def delete_certificate_entry(self, invoice_id, invoice_type, product_id, certificate_type, invoice_item_id=None):
        with self.transaction():
            if invoice_item_id is not None:
                self.cursor.execute(
                    "DELETE FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s AND invoice_item_id=%s AND certificate_type=%s",
                    (invoice_id, invoice_type, invoice_item_id, certificate_type),
                )
            else:
                self.cursor.execute(
                    "DELETE FROM certificate_entry WHERE invoice_id=%s AND invoice_type=%s AND product_id=%s AND certificate_type=%s",
                    (invoice_id, invoice_type, product_id, certificate_type),
                )

    def replace_certificate_entry_type(self, invoice_id, invoice_type, product_id, active_certificate_type, invoice_item_id=None):
        for certificate_type in self.get_certificate_types():
            if certificate_type == active_certificate_type:
                continue
            self.delete_certificate_entry(invoice_id, invoice_type, product_id, certificate_type, invoice_item_id=invoice_item_id)
    
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

  