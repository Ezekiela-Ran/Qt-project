from contextlib import contextmanager
from pathlib import Path

from models.database.db_config import CLIENT_DEPLOYMENT_ROLE, get_database_settings
from models.database.sqlite_backend import connect as connect_sqlite

class Tables:
    def __init__(self):
        self.settings = get_database_settings()
        self.backend = self.settings['engine']
        self.database_name = Path(self.settings['sqlite_path']).name
        self._transaction_depth = 0
        create_if_missing = self.settings.get('deployment_role') != CLIENT_DEPLOYMENT_ROLE
        try:
            self.conn = connect_sqlite(Path(self.settings['sqlite_path']), create_if_missing=create_if_missing)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Base SQLite partagée introuvable. Vérifiez le chemin réseau configuré et le partage Windows du poste hôte."
            ) from exc
        self.cursor = self.conn.cursor(dictionary=True)

    @property
    def is_mysql(self) -> bool:
        return False

    @property
    def is_sqlite(self) -> bool:
        return self.backend == "sqlite"

    def column_exists(self, table_name: str, column_name: str) -> bool:
        if self.is_mysql:
            self.cursor.execute(
                "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                (table_name, column_name),
            )
            row = self.cursor.fetchone()
            return bool(row and row["cnt"])

        self.cursor.execute(f"PRAGMA table_info({table_name})")
        return any(row["name"] == column_name for row in self.cursor.fetchall())

    def index_exists(self, index_name: str) -> bool:
        if self.is_mysql:
            self.cursor.execute(
                "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND INDEX_NAME = %s",
                (index_name,),
            )
            row = self.cursor.fetchone()
            return bool(row and row["cnt"])

        self.cursor.execute("SELECT COUNT(*) AS cnt FROM sqlite_master WHERE type = 'index' AND name = %s", (index_name,))
        row = self.cursor.fetchone()
        return bool(row and row["cnt"])

    def list_live_tables(self):
        if self.is_mysql:
            self.cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME NOT LIKE '%archive_%'"
            )
            return [row['TABLE_NAME'] for row in self.cursor.fetchall()]

        self.cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%archive_%'"
        )
        return [row['name'] for row in self.cursor.fetchall()]

    def set_foreign_keys(self, enabled: bool):
        if self.is_mysql:
            self.cursor.execute(f"SET FOREIGN_KEY_CHECKS={1 if enabled else 0}")
        else:
            self.cursor.execute(f"PRAGMA foreign_keys = {'ON' if enabled else 'OFF'}")

    def reset_table_sequence(self, table_name: str, next_id: int = 1):
        if self.is_mysql:
            self.cursor.execute(f"ALTER TABLE {table_name} AUTO_INCREMENT = {max(int(next_id), 1)}")
            return

        self.cursor.execute("DELETE FROM sqlite_sequence WHERE name = %s", (table_name,))
        if int(next_id) > 1:
            self.cursor.execute(
                "INSERT INTO sqlite_sequence(name, seq) VALUES (%s, %s)",
                (table_name, int(next_id) - 1),
            )

    def proforma_invoice_table(self):
        if self.is_mysql:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS proforma_invoice (
                id INT AUTO_INCREMENT PRIMARY KEY,
                company_name VARCHAR(255) NOT NULL,
                nif VARCHAR(255),
                stat VARCHAR(255),
                date DATE NOT NULL,
                resp VARCHAR(255) NOT NULL,
                total DECIMAL(10,2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            return

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS proforma_invoice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            nif TEXT,
            stat TEXT,
            date TEXT NOT NULL,
            resp TEXT NOT NULL,
            total REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    def standard_invoice_table(self):
        if self.is_mysql:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS standard_invoice (
                id INT AUTO_INCREMENT PRIMARY KEY,
                company_name VARCHAR(255) NOT NULL,
                stat VARCHAR(255),
                nif VARCHAR(255),
                address VARCHAR(255),
                date_issue DATE NOT NULL,
                date_result DATE NOT NULL,
                product_ref VARCHAR(255) NOT NULL,
                resp VARCHAR(255) NOT NULL,
                total DECIMAL(10,2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            return

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS standard_invoice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            stat TEXT,
            nif TEXT,
            address TEXT,
            date_issue TEXT NOT NULL,
            date_result TEXT NOT NULL,
            product_ref TEXT NOT NULL,
            resp TEXT NOT NULL,
            total REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    def product_type_table(self):
        if self.is_mysql:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_type (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_type_name VARCHAR(255) NOT NULL
            )
            """)
            return

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_type (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_type_name TEXT NOT NULL
        )
        """)

    def products_table(self):
        if self.is_mysql:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_name VARCHAR(255) NOT NULL,
                default_quantity INT NOT NULL DEFAULT 1,
                analysis_duration_days INT NOT NULL DEFAULT 0,
                ref_b_analyse INT NOT NULL,
                num_act VARCHAR(191),
                physico INT,
                micro INT,
                toxico INT,
                subtotal INT,
                product_type_id INT NOT NULL,
                UNIQUE KEY uk_products_num_act (num_act),
                FOREIGN KEY (product_type_id)
                REFERENCES product_type(id)
                ON DELETE CASCADE
            )
            """)
            return

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            default_quantity INTEGER NOT NULL DEFAULT 1,
            analysis_duration_days INTEGER NOT NULL DEFAULT 0,
            ref_b_analyse INTEGER NOT NULL,
            num_act TEXT,
            physico INTEGER,
            micro INTEGER,
            toxico INTEGER,
            subtotal INTEGER,
            product_type_id INTEGER NOT NULL,
            FOREIGN KEY (product_type_id) REFERENCES product_type(id) ON DELETE CASCADE
        )
        """)
        self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS uk_products_num_act ON products(num_act)")

    def invoice_client_table(self):
        if self.is_mysql:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoice_client (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_id INT NOT NULL,
                invoice_type ENUM('standard', 'proforma') NOT NULL,
                product_id INT NOT NULL,
                ref_b_analyse INT NULL,
                num_act VARCHAR(255) NULL,
                result_date VARCHAR(32) NULL,
                quantity INT DEFAULT 1,
                physico DECIMAL(10,2) DEFAULT 0,
                micro DECIMAL(10,2) DEFAULT 0,
                toxico DECIMAL(10,2) DEFAULT 0,
                subtotal DECIMAL(10,2) DEFAULT 0,
                total DECIMAL(10,2) DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
            """)
            return

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_client (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            invoice_type TEXT NOT NULL CHECK (invoice_type IN ('standard', 'proforma')),
            product_id INTEGER NOT NULL,
            ref_b_analyse INTEGER NULL,
            num_act TEXT NULL,
            result_date TEXT NULL,
            quantity INTEGER DEFAULT 1,
            physico REAL DEFAULT 0,
            micro REAL DEFAULT 0,
            toxico REAL DEFAULT 0,
            subtotal REAL DEFAULT 0,
            total REAL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """)

    def certificate_entry_table(self):
        if self.is_mysql:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS certificate_entry (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_id INT NOT NULL,
                invoice_type ENUM('standard', 'proforma') NOT NULL,
                product_id INT NOT NULL,
                invoice_item_id INT NULL,
                certificate_type ENUM('CC', 'CNC', 'CP', 'CNP', 'CCON', 'CNCON') NOT NULL,
                quantity VARCHAR(255),
                quantity_analysee VARCHAR(255),
                num_lot VARCHAR(255),
                num_act VARCHAR(255),
                num_cert VARCHAR(255),
                classe VARCHAR(255),
                date_production VARCHAR(32),
                date_production_modified TINYINT(1) NULL,
                date_peremption VARCHAR(32),
                date_peremption_modified TINYINT(1) NULL,
                num_prl VARCHAR(255),
                date_commerce VARCHAR(32),
                date_commerce_modified TINYINT(1) NULL,
                date_cert VARCHAR(32),
                date_cert_modified TINYINT(1) NULL,
                printed_at VARCHAR(32) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uk_certificate_entry_scope (invoice_id, invoice_type, invoice_item_id, certificate_type),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            )
            """)
            return

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS certificate_entry (
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
        """)
        self.cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uk_certificate_entry_scope ON certificate_entry(invoice_id, invoice_type, invoice_item_id, certificate_type)"
        )

    def app_settings_table(self):
        if self.is_mysql:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key VARCHAR(191) PRIMARY KEY,
                setting_value VARCHAR(255) NOT NULL
            )
            """)
            return

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        )
        """)

    def users_table(self):
        if self.is_mysql:
            self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(191) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(32) NOT NULL DEFAULT 'user',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            return

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    def close(self):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

    def commit_if_needed(self):
        if self._transaction_depth == 0:
            self.conn.commit()

    @contextmanager
    def transaction(self):
        started = self._transaction_depth == 0
        if started:
            if self.is_mysql:
                self.conn.start_transaction()
            else:
                self.cursor.execute("BEGIN IMMEDIATE")
        self._transaction_depth += 1
        try:
            yield
        except Exception:
            self._transaction_depth -= 1
            if started:
                self.conn.rollback()
            raise
        else:
            self._transaction_depth -= 1
            if started:
                self.conn.commit()
