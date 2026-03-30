from pathlib import Path
import os
import sys


def get_project_base_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def resolve_resource_path(relative_path: str) -> Path:
    return get_project_base_path() / relative_path


def get_app_data_dir(app_name: str = "FaC") -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / app_name
    return Path.home() / f".{app_name.lower()}"
