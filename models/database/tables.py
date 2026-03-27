from pathlib import Path

from models.database.db_config import DB_CONFIG, DB_ENGINE, DB_NAME, DB_PATH
from models.database.sqlite_backend import connect as connect_sqlite

try:
    import mysql.connector
except Exception:
    mysql = None

class Tables:
    def __init__(self):
        self.backend = DB_ENGINE
        if self.backend == "mysql":
            if mysql is None:
                raise RuntimeError("mysql-connector-python n'est pas disponible.")
            self.conn = mysql.connector.connect(**DB_CONFIG)
            # Ensure each statement sees up-to-date data across multiple app connections.
            self.conn.autocommit = True
        else:
            self.conn = connect_sqlite(Path(DB_PATH))
        self.cursor = self.conn.cursor(dictionary=True)
        if self.is_mysql:
            self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
            self.cursor.execute(f"USE `{DB_NAME}`")
            self.cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")

    @property
    def is_mysql(self) -> bool:
        return self.backend == "mysql"

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
            quantity INTEGER DEFAULT 1,
            physico REAL DEFAULT 0,
            micro REAL DEFAULT 0,
            toxico REAL DEFAULT 0,
            subtotal REAL DEFAULT 0,
            total REAL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        """)

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
