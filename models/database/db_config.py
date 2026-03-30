import json
import os
import socket
from pathlib import Path

from utils.path_utils import get_app_data_dir

try:
    import mysql.connector
except Exception:
    mysql = None

from models.database.sqlite_backend import connect as connect_sqlite


DEFAULT_DB_NAME = 'invoicing'
DEFAULT_DB_ENGINE = 'mysql'
DEFAULT_DB_HOST = '127.0.0.1'
DEFAULT_DB_PORT = 3306
DEFAULT_DB_USER = 'lfca_app'
DEFAULT_DB_PASSWORD = 'lfca_app'


def build_default_database_config() -> dict:
    return {
        'engine': DEFAULT_DB_ENGINE,
        'sqlite_path': _default_sqlite_path(),
        'deployment_role': 'client',
        'setup_completed': False,
        'server_host_hint': '',
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
    inferred_setup_completed = bool(
        raw_config.get('setup_completed')
        or str(raw_config.get('server_host_hint') or '').strip()
        or (
            isinstance(mysql_config, dict)
            and str(mysql_config.get('host') or '').strip()
            and str(mysql_config.get('host') or '').strip() != DEFAULT_DB_HOST
        )
        or str(raw_config.get('deployment_role') or '').strip().lower() == 'server'
    )

    return {
        'engine': _normalize_engine(raw_config.get('engine')),
        'sqlite_path': _expand_path(raw_config.get('sqlite_path') or defaults['sqlite_path']),
        'deployment_role': str(raw_config.get('deployment_role') or defaults.get('deployment_role') or 'client').strip().lower() or 'client',
        'setup_completed': inferred_setup_completed,
        'server_host_hint': str(raw_config.get('server_host_hint') or defaults.get('server_host_hint') or '').strip(),
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
        'deployment_role': str(file_config.get('deployment_role') or 'client').strip().lower() or 'client',
        'setup_completed': bool(file_config.get('setup_completed')),
        'server_host_hint': str(file_config.get('server_host_hint') or '').strip(),
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


def database_config_requires_setup() -> bool:
    settings = get_database_settings()
    if settings['env_overrides']:
        return False

    config_file = Path(settings['config_file'])
    if not config_file.exists():
        return True

    if settings['engine'] != 'mysql':
        return True

    if not settings.get('setup_completed'):
        return True

    mysql_settings = settings['mysql']
    return not all(
        [
            mysql_settings.get('host'),
            mysql_settings.get('user'),
            mysql_settings.get('database'),
        ]
    )


def _quote_mysql_string(value: str) -> str:
    return "'" + str(value or '').replace("\\", "\\\\").replace("'", "''") + "'"


def _quote_mysql_identifier(value: str) -> str:
    return "`" + str(value or '').replace("`", "``") + "`"


def detect_local_ipv4_addresses() -> list[str]:
    addresses = []

    try:
        probe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe_socket.connect(("8.8.8.8", 80))
            primary_ip = probe_socket.getsockname()[0]
            if primary_ip and not primary_ip.startswith("127."):
                addresses.append(primary_ip)
        finally:
            probe_socket.close()
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for result in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            ip_address = result[4][0]
            if ip_address and not ip_address.startswith("127.") and ip_address not in addresses:
                addresses.append(ip_address)
    except OSError:
        pass

    if not addresses:
        addresses.append("127.0.0.1")
    return addresses


def build_server_database_config(server_ip: str, database: str = DEFAULT_DB_NAME, port: int = DEFAULT_DB_PORT) -> dict:
    return normalize_database_config(
        {
            'engine': 'mysql',
            'deployment_role': 'server',
            'setup_completed': True,
            'server_host_hint': server_ip,
            'mysql': {
                'host': '127.0.0.1',
                'port': port,
                'user': DEFAULT_DB_USER,
                'password': DEFAULT_DB_PASSWORD,
                'database': database,
            },
        }
    )


def build_client_database_config(server_ip: str, database: str = DEFAULT_DB_NAME, port: int = DEFAULT_DB_PORT) -> dict:
    return normalize_database_config(
        {
            'engine': 'mysql',
            'deployment_role': 'client',
            'setup_completed': True,
            'server_host_hint': server_ip,
            'mysql': {
                'host': str(server_ip or '').strip(),
                'port': port,
                'user': DEFAULT_DB_USER,
                'password': DEFAULT_DB_PASSWORD,
                'database': database,
            },
        }
    )


def bootstrap_mysql_server(admin_user: str, admin_password: str, database: str = DEFAULT_DB_NAME, port: int = DEFAULT_DB_PORT):
    if mysql is None:
        raise RuntimeError("mysql-connector-python n'est pas disponible.")

    normalized_admin_user = str(admin_user or '').strip()
    if not normalized_admin_user:
        raise ValueError("Le compte administrateur MySQL est obligatoire.")

    database_name = str(database or DEFAULT_DB_NAME).strip() or DEFAULT_DB_NAME
    conn = mysql.connector.connect(
        host='127.0.0.1',
        port=int(port),
        user=normalized_admin_user,
        password=str(admin_password or ''),
    )
    cursor = conn.cursor()
    try:
        quoted_database = _quote_mysql_identifier(database_name)
        app_user_local = _quote_mysql_string(DEFAULT_DB_USER)
        app_password_local = _quote_mysql_string(DEFAULT_DB_PASSWORD)
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {quoted_database}")
        cursor.execute(f"CREATE USER IF NOT EXISTS {app_user_local}@'localhost' IDENTIFIED BY {app_password_local}")
        cursor.execute(f"ALTER USER {app_user_local}@'localhost' IDENTIFIED BY {app_password_local}")
        cursor.execute(f"CREATE USER IF NOT EXISTS {app_user_local}@'%' IDENTIFIED BY {app_password_local}")
        cursor.execute(f"ALTER USER {app_user_local}@'%' IDENTIFIED BY {app_password_local}")
        cursor.execute(f"GRANT ALL PRIVILEGES ON {quoted_database}.* TO {app_user_local}@'localhost'")
        cursor.execute(f"GRANT ALL PRIVILEGES ON {quoted_database}.* TO {app_user_local}@'%'")
        cursor.execute("FLUSH PRIVILEGES")
        conn.commit()
    finally:
        cursor.close()
        conn.close()


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