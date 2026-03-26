import os

from utils.path_utils import get_app_data_dir


def _get_port() -> int:
    raw_port = os.getenv('DB_PORT', '3306')
    try:
        return int(raw_port)
    except ValueError:
        return 3306


DB_NAME = os.getenv('DB_NAME', 'invoicing')
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite').strip().lower()
DB_PATH = os.getenv('DB_PATH', str(get_app_data_dir('LFCA') / 'lfca.db'))


# Configuration de la base de données
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': _get_port(),
    'user': os.getenv('DB_USER', 'sam'),
    'password': os.getenv('DB_PASSWORD', ''),
}