import json
import os
import shutil
import socket
from pathlib import Path

from models.database.sqlite_backend import connect as connect_sqlite
from utils.path_utils import get_app_data_dir, get_public_documents_dir


DEFAULT_DB_ENGINE = 'sqlite'
DEFAULT_DEPLOYMENT_ROLE = ''
HOST_DEPLOYMENT_ROLE = 'host'
CLIENT_DEPLOYMENT_ROLE = 'client'
APP_DATA_DIR_NAME = 'FacCP'
LEGACY_APP_DATA_DIR_NAMES = ('FaC', 'LFCA')
APP_DB_CONFIG_ENV = 'FACCP_DB_CONFIG'
LEGACY_APP_DB_CONFIG_ENVS = ('FAC_DB_CONFIG', 'LFCA_DB_CONFIG')
DEFAULT_SQLITE_FILENAME = 'faccp.db'
LEGACY_SQLITE_FILENAMES = ('fac.db', 'lfca.db')
DEFAULT_SHARED_FOLDER_NAME = 'FacCP'


def build_default_database_config() -> dict:
    return {
        'engine': DEFAULT_DB_ENGINE,
        'deployment_role': DEFAULT_DEPLOYMENT_ROLE,
        'setup_completed': False,
        'sqlite_path': _default_host_database_path(),
        'shared_database_path': '',
        'host_display_name': '',
        'host_ip_hint': '',
    }


def _primary_config_path() -> Path:
    return get_app_data_dir(APP_DATA_DIR_NAME) / 'database.json'


def _legacy_config_paths() -> list[Path]:
    return [get_app_data_dir(app_name) / 'database.json' for app_name in LEGACY_APP_DATA_DIR_NAMES]


def _default_host_database_path_obj() -> Path:
    return get_public_documents_dir(DEFAULT_SHARED_FOLDER_NAME) / DEFAULT_SQLITE_FILENAME


def _legacy_sqlite_path_candidates() -> list[Path]:
    candidates = []
    for app_name in LEGACY_APP_DATA_DIR_NAMES:
        for filename in LEGACY_SQLITE_FILENAMES:
            candidates.append(get_app_data_dir(app_name) / filename)
    return candidates


def _find_first_existing_path(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _migrate_legacy_sqlite_database(target_path: Path):
    if target_path.exists():
        return

    legacy_path = _find_first_existing_path(_legacy_sqlite_path_candidates())
    if legacy_path is None:
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy_path, target_path)


def _config_file_candidates() -> list[Path]:
    candidates = []
    for env_key in (APP_DB_CONFIG_ENV, *LEGACY_APP_DB_CONFIG_ENVS):
        custom_path = os.getenv(env_key, '').strip()
        if custom_path:
            candidates.append(Path(os.path.expandvars(custom_path)).expanduser())
    candidates.extend(_legacy_config_paths())
    candidates.append(_primary_config_path())
    candidates.append(Path.cwd() / 'database.json')
    return candidates


def _default_host_database_path() -> str:
    target_path = _default_host_database_path_obj()
    _migrate_legacy_sqlite_database(target_path)
    return str(target_path)


def _normalize_sqlite_path(value: str, *, fallback_to_default: bool) -> str:
    raw_path = os.path.expandvars(str(value or '')).strip()
    target_path = _default_host_database_path_obj()

    if not raw_path:
        if fallback_to_default:
            _migrate_legacy_sqlite_database(target_path)
            return str(target_path)
        return ''

    normalized_path = Path(raw_path).expanduser()
    for legacy_path in _legacy_sqlite_path_candidates():
        if normalized_path == legacy_path:
            _migrate_legacy_sqlite_database(target_path)
            return str(target_path)

    if normalized_path == target_path:
        _migrate_legacy_sqlite_database(target_path)

    return str(normalized_path)


def _write_default_config_template(config_path: Path):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        return

    config_path.write_text(json.dumps(build_default_database_config(), indent=2), encoding='utf-8')


def _normalize_role(value) -> str:
    role = str(value or '').strip().lower()
    if role == 'server':
        return HOST_DEPLOYMENT_ROLE
    if role in {HOST_DEPLOYMENT_ROLE, CLIENT_DEPLOYMENT_ROLE}:
        return role
    return DEFAULT_DEPLOYMENT_ROLE


def normalize_database_config(raw_config: dict | None) -> dict:
    defaults = build_default_database_config()
    raw_config = raw_config if isinstance(raw_config, dict) else {}

    legacy_mysql_configured = str(raw_config.get('engine') or '').strip().lower() == 'mysql' or isinstance(raw_config.get('mysql'), dict)
    role = _normalize_role(raw_config.get('deployment_role'))
    raw_sqlite_path = raw_config.get('sqlite_path')
    raw_shared_path = raw_config.get('shared_database_path')
    explicit_setup = bool(raw_config.get('setup_completed'))

    if role == DEFAULT_DEPLOYMENT_ROLE and not legacy_mysql_configured and explicit_setup and raw_sqlite_path:
        role = HOST_DEPLOYMENT_ROLE
        explicit_setup = True

    if role == HOST_DEPLOYMENT_ROLE:
        sqlite_path = _normalize_sqlite_path(raw_sqlite_path or defaults['sqlite_path'], fallback_to_default=True)
        shared_database_path = _normalize_sqlite_path(raw_shared_path or sqlite_path, fallback_to_default=False)
        setup_completed = explicit_setup and bool(sqlite_path)
    elif role == CLIENT_DEPLOYMENT_ROLE:
        sqlite_path = _normalize_sqlite_path(raw_shared_path or raw_sqlite_path, fallback_to_default=False)
        shared_database_path = sqlite_path
        setup_completed = explicit_setup and bool(sqlite_path)
    else:
        sqlite_path = _normalize_sqlite_path(raw_sqlite_path or defaults['sqlite_path'], fallback_to_default=True)
        shared_database_path = ''
        setup_completed = False

    return {
        'engine': DEFAULT_DB_ENGINE,
        'deployment_role': role,
        'setup_completed': setup_completed and not legacy_mysql_configured,
        'sqlite_path': sqlite_path,
        'shared_database_path': shared_database_path,
        'host_display_name': str(raw_config.get('host_display_name') or '').strip(),
        'host_ip_hint': str(raw_config.get('host_ip_hint') or '').strip(),
    }


def _load_file_config() -> tuple[dict, Path]:
    candidates = _config_file_candidates()
    primary_path = _primary_config_path()

    _write_default_config_template(primary_path)

    primary_normalized = build_default_database_config()
    if primary_path.exists():
        try:
            loaded_primary = json.loads(primary_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            loaded_primary = None
        if isinstance(loaded_primary, dict):
            primary_normalized = normalize_database_config(loaded_primary)
            if primary_normalized.get('setup_completed'):
                return primary_normalized, primary_path

    for candidate in candidates:
        if candidate == primary_path:
            continue
        if not candidate.exists():
            continue
        try:
            loaded = json.loads(candidate.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(loaded, dict):
            normalized = normalize_database_config(loaded)
            if normalized.get('setup_completed'):
                save_database_config(normalized, primary_path)
                return normalized, primary_path

    return primary_normalized, primary_path


def _pick_setting(env_key: str, file_value, default_value):
    env_value = os.getenv(env_key)
    if env_value is not None and str(env_value).strip() != '':
        return env_value
    if file_value is not None and str(file_value).strip() != '':
        return file_value
    return default_value


def get_database_settings() -> dict:
    file_config, config_file = _load_file_config()
    sqlite_path = _normalize_sqlite_path(
        _pick_setting('DB_PATH', file_config.get('sqlite_path'), _default_host_database_path()),
        fallback_to_default=True,
    )
    deployment_role = _normalize_role(file_config.get('deployment_role'))
    if deployment_role == CLIENT_DEPLOYMENT_ROLE and not os.getenv('DB_PATH'):
        sqlite_path = _normalize_sqlite_path(file_config.get('shared_database_path') or sqlite_path, fallback_to_default=False)

    return {
        'engine': DEFAULT_DB_ENGINE,
        'sqlite_path': sqlite_path,
        'shared_database_path': str(file_config.get('shared_database_path') or '').strip(),
        'deployment_role': deployment_role,
        'setup_completed': bool(file_config.get('setup_completed')),
        'host_display_name': str(file_config.get('host_display_name') or '').strip(),
        'host_ip_hint': str(file_config.get('host_ip_hint') or '').strip(),
        'config_file': config_file,
        'env_overrides': {
            key: os.getenv(key)
            for key in ('DB_PATH',)
            if os.getenv(key) not in (None, '')
        },
    }


def database_config_requires_setup() -> bool:
    settings = get_database_settings()
    if settings['env_overrides']:
        return False

    config_file = Path(settings['config_file'])
    if not config_file.exists():
        return True

    if settings['deployment_role'] not in {HOST_DEPLOYMENT_ROLE, CLIENT_DEPLOYMENT_ROLE}:
        return True

    if not settings.get('setup_completed'):
        return True

    if settings['deployment_role'] == CLIENT_DEPLOYMENT_ROLE:
        return not bool(settings.get('shared_database_path'))

    return not bool(settings.get('sqlite_path'))


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


def build_host_database_config(database_path: str | None = None, *, host_display_name: str = '', host_ip_hint: str = '') -> dict:
    return normalize_database_config(
        {
            'engine': DEFAULT_DB_ENGINE,
            'deployment_role': HOST_DEPLOYMENT_ROLE,
            'setup_completed': True,
            'sqlite_path': database_path or _default_host_database_path(),
            'shared_database_path': database_path or _default_host_database_path(),
            'host_display_name': host_display_name,
            'host_ip_hint': host_ip_hint,
        }
    )


def build_client_database_config(shared_database_path: str, *, host_display_name: str = '', host_ip_hint: str = '') -> dict:
    return normalize_database_config(
        {
            'engine': DEFAULT_DB_ENGINE,
            'deployment_role': CLIENT_DEPLOYMENT_ROLE,
            'setup_completed': True,
            'sqlite_path': shared_database_path,
            'shared_database_path': shared_database_path,
            'host_display_name': host_display_name,
            'host_ip_hint': host_ip_hint,
        }
    )


def save_database_config(config: dict, config_path: Path | None = None) -> Path:
    normalized = normalize_database_config(config)
    target_path = Path(config_path) if config_path else _primary_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(normalized, indent=2), encoding='utf-8')
    return target_path


def test_database_connection(config: dict | None = None):
    normalized = normalize_database_config(config) if config is not None else get_database_settings()
    sqlite_path = str(normalized.get('sqlite_path') or '').strip()
    if not sqlite_path:
        raise ValueError("Le chemin de la base SQLite est obligatoire.")

    database_path = Path(sqlite_path)
    create_if_missing = normalized.get('deployment_role') != CLIENT_DEPLOYMENT_ROLE
    if not create_if_missing and not database_path.exists():
        raise FileNotFoundError(
            "Le fichier SQLite partagé est introuvable. Vérifiez le chemin réseau et le partage Windows."
        )

    conn = connect_sqlite(database_path, create_if_missing=create_if_missing)
    conn.close()


FILE_CONFIG, DB_CONFIG_FILE = _load_file_config()
DB_NAME = Path(get_database_settings()['sqlite_path']).name
DB_ENGINE = get_database_settings()['engine']
DB_PATH = get_database_settings()['sqlite_path']
DB_CONFIG = {
    'sqlite_path': get_database_settings()['sqlite_path'],
    'deployment_role': get_database_settings()['deployment_role'],
}