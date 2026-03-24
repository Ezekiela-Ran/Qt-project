from models.database.db_config import DB_CONFIG
import mysql.connector

class Tables:
    def __init__(self):
        self.conn = mysql.connector.connect(**DB_CONFIG)
        # Ensure each statement sees up-to-date data across multiple app connections.
        self.conn.autocommit = True
        self.cursor = self.conn.cursor(dictionary=True)
        self.cursor.execute("CREATE DATABASE IF NOT EXISTS invoicing")
        self.cursor.execute("USE invoicing")
        self.cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")

    def proforma_invoice_table(self):
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

    def standard_invoice_table(self):
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

    def product_type_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_type (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_type_name VARCHAR(255) NOT NULL
        )
        """)

    def products_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_name VARCHAR(255) NOT NULL,
            ref_b_analyse INT NOT NULL,
            num_act VARCHAR(255),
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

    def invoice_client_table(self):
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

    def app_settings_table(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key VARCHAR(255) PRIMARY KEY,
            setting_value VARCHAR(255) NOT NULL
        )
        """)

    def close(self):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()
