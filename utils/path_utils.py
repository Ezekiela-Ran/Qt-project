from pathlib import Path
import os
import sys


def get_project_base_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def resolve_resource_path(relative_path: str) -> Path:
    return get_project_base_path() / relative_path


def get_app_data_dir(app_name: str = "FacCP") -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / app_name
    return Path.home() / f".{app_name.lower()}"


def get_public_documents_dir(app_name: str = "FacCP") -> Path:
    public_root = os.getenv("PUBLIC")
    if public_root:
        return Path(public_root) / "Documents" / app_name
    return Path.home().parent / "Public" / "Documents" / app_name
