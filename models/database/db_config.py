import json
import os
from pathlib import Path

from utils.path_utils import get_app_data_dir

try:
    import mysql.connector
except Exception:
    mysql = None

from models.database.sqlite_backend import connect as connect_sqlite


DEFAULT_DB_NAME = 'invoicing'
DEFAULT_DB_ENGINE = 'sqlite'
DEFAULT_DB_HOST = 'localhost'
DEFAULT_DB_PORT = 3306
DEFAULT_DB_USER = 'sam'
DEFAULT_DB_PASSWORD = ''


def build_default_database_config() -> dict:
    return {
        'engine': DEFAULT_DB_ENGINE,
        'sqlite_path': _default_sqlite_path(),
        'mysql': {
            'host': DEFAULT_DB_HOST,
            'port': DEFAULT_DB_PORT,
            'user': DEFAULT_DB_USER,
            'password': DEFAULT_DB_PASSWORD,
            'database': DEFAULT_DB_NAME,
        },
    }


def _config_file_candidates() -> list[Path]:
    custom_path = os.getenv('LFCA_DB_CONFIG', '').strip()
    candidates = []
    if custom_path:
        candidates.append(Path(os.path.expandvars(custom_path)).expanduser())
    candidates.append(get_app_data_dir('LFCA') / 'database.json')
    candidates.append(Path.cwd() / 'database.json')
    return candidates


def _default_sqlite_path() -> str:
    return str(get_app_data_dir('LFCA') / 'lfca.db')


def _write_default_config_template(config_path: Path):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        return

    config_path.write_text(
        json.dumps(build_default_database_config(), indent=2),
        encoding='utf-8',
    )


def _normalize_engine(value) -> str:
    engine = str(value or DEFAULT_DB_ENGINE).strip().lower()
    return engine if engine in {'sqlite', 'mysql'} else DEFAULT_DB_ENGINE


def normalize_database_config(raw_config: dict | None) -> dict:
    defaults = build_default_database_config()
    raw_config = raw_config if isinstance(raw_config, dict) else {}
    mysql_config = raw_config.get('mysql') if isinstance(raw_config.get('mysql'), dict) else {}

    return {
        'engine': _normalize_engine(raw_config.get('engine')),
        'sqlite_path': _expand_path(raw_config.get('sqlite_path') or defaults['sqlite_path']),
        'mysql': {
            'host': str(mysql_config.get('host') or defaults['mysql']['host']).strip() or DEFAULT_DB_HOST,
            'port': _coerce_port(mysql_config.get('port'), DEFAULT_DB_PORT),
            'user': str(mysql_config.get('user') or defaults['mysql']['user']).strip(),
            'password': str(mysql_config.get('password') or defaults['mysql']['password']),
            'database': str(mysql_config.get('database') or defaults['mysql']['database']).strip() or DEFAULT_DB_NAME,
        },
    }


def _load_file_config() -> tuple[dict, Path]:
    candidates = _config_file_candidates()
    primary_path = get_app_data_dir('LFCA') / 'database.json'
    _write_default_config_template(primary_path)

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            loaded = json.loads(candidate.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(loaded, dict):
            return normalize_database_config(loaded), candidate
    return build_default_database_config(), primary_path


def _pick_setting(env_key: str, file_value, default_value):
    env_value = os.getenv(env_key)
    if env_value is not None and str(env_value).strip() != '':
        return env_value
    if file_value is not None and str(file_value).strip() != '':
        return file_value
    return default_value


def _expand_path(value: str) -> str:
    return os.path.expandvars(str(value or '')).strip()


def _coerce_port(value, default_value: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default_value)


def _get_port() -> int:
    file_config, _ = _load_file_config()
    raw_port = _pick_setting('DB_PORT', file_config['mysql'].get('port'), DEFAULT_DB_PORT)
    return _coerce_port(raw_port, DEFAULT_DB_PORT)


def get_database_settings() -> dict:
    file_config, config_file = _load_file_config()
    mysql_file_config = file_config['mysql']
    engine = _normalize_engine(_pick_setting('DB_ENGINE', file_config.get('engine'), DEFAULT_DB_ENGINE))
    database_name = str(_pick_setting('DB_NAME', mysql_file_config.get('database'), DEFAULT_DB_NAME)).strip() or DEFAULT_DB_NAME
    sqlite_path = _expand_path(_pick_setting('DB_PATH', file_config.get('sqlite_path'), _default_sqlite_path()))

    settings = {
        'engine': engine,
        'sqlite_path': sqlite_path,
        'mysql': {
            'host': str(_pick_setting('DB_HOST', mysql_file_config.get('host'), DEFAULT_DB_HOST)).strip() or DEFAULT_DB_HOST,
            'port': _get_port(),
            'user': str(_pick_setting('DB_USER', mysql_file_config.get('user'), DEFAULT_DB_USER)).strip(),
            'password': str(_pick_setting('DB_PASSWORD', mysql_file_config.get('password'), DEFAULT_DB_PASSWORD)),
            'database': database_name,
        },
        'config_file': config_file,
        'env_overrides': {
            key: os.getenv(key)
            for key in ('DB_ENGINE', 'DB_PATH', 'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME')
            if os.getenv(key) not in (None, '')
        },
    }
    return settings


def save_database_config(config: dict, config_path: Path | None = None) -> Path:
    normalized = normalize_database_config(config)
    target_path = Path(config_path) if config_path else get_app_data_dir('LFCA') / 'database.json'
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(normalized, indent=2), encoding='utf-8')
    return target_path


def test_database_connection(config: dict | None = None):
    normalized = normalize_database_config(config) if config is not None else get_database_settings()
    engine = normalized['engine']
    if engine == 'sqlite':
        conn = connect_sqlite(Path(normalized['sqlite_path']))
        conn.close()
        return

    if mysql is None:
        raise RuntimeError("mysql-connector-python n'est pas disponible.")

    db_name = str(normalized['mysql']['database']).replace('`', '``')
    conn = mysql.connector.connect(
        host=normalized['mysql']['host'],
        port=normalized['mysql']['port'],
        user=normalized['mysql']['user'],
        password=normalized['mysql']['password'],
    )
    cursor = conn.cursor()
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        cursor.execute(f"USE `{db_name}`")
        cursor.execute("SELECT 1")
        cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


FILE_CONFIG, DB_CONFIG_FILE = _load_file_config()
DB_NAME = get_database_settings()['mysql']['database']
DB_ENGINE = get_database_settings()['engine']
DB_PATH = get_database_settings()['sqlite_path']
DB_CONFIG = {
    'host': get_database_settings()['mysql']['host'],
    'port': get_database_settings()['mysql']['port'],
    'user': get_database_settings()['mysql']['user'],
    'password': get_database_settings()['mysql']['password'],
}