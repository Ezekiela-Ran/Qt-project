from models.database_manager import DatabaseManager
from utils.auth_utils import hash_password, verify_password


class AuthService:
    def __init__(self):
        self.db = DatabaseManager()

    @staticmethod
    def _normalize_username(username: str) -> str:
        return str(username or "").strip()

    @staticmethod
    def _normalize_role(role: str) -> str:
        normalized_role = str(role or "user").strip().lower()
        return normalized_role if normalized_role in {"admin", "user"} else "user"

    def has_any_user(self) -> bool:
        return self.db.count_users() > 0

    def has_admin(self) -> bool:
        return self.db.count_admin_users() > 0

    def authenticate(self, username: str, password: str):
        normalized_username = self._normalize_username(username)
        if not normalized_username or not password:
            return None

        user = self.db.get_user_by_username(normalized_username, include_password_hash=True)
        if not user or not int(user.get("is_active") or 0):
            return None
        if not verify_password(password, user.get("password_hash")):
            return None

        user.pop("password_hash", None)
        return user

    def create_initial_admin(self, username: str, password: str):
        if self.has_admin():
            raise ValueError("Un administrateur existe déjà.")
        return self.create_user(username, password, role="admin")

    def create_user(self, username: str, password: str, role: str = "user", is_active: bool = True):
        normalized_username = self._normalize_username(username)
        if not normalized_username:
            raise ValueError("Le nom d'utilisateur est obligatoire.")
        if self.db.get_user_by_username(normalized_username, include_password_hash=False):
            raise ValueError("Ce nom d'utilisateur existe déjà.")
        password_hash = hash_password(password)
        user_id = self.db.create_user(normalized_username, password_hash, role=self._normalize_role(role), is_active=is_active)
        return self.db.get_user_by_id(user_id, include_password_hash=False)

    def list_users(self):
        return self.db.list_users()

    def update_user(self, user_id: int, username: str, role: str, is_active: bool = True):
        normalized_username = self._normalize_username(username)
        normalized_role = self._normalize_role(role)
        if not normalized_username:
            raise ValueError("Le nom d'utilisateur est obligatoire.")

        existing = self.db.get_user_by_username(normalized_username, include_password_hash=False)
        if existing and existing.get("id") != user_id:
            raise ValueError("Ce nom d'utilisateur existe déjà.")

        current_user = self.db.get_user_by_id(user_id, include_password_hash=False)
        if not current_user:
            raise ValueError("Utilisateur introuvable.")
        if str(current_user.get("role") or "").lower() == "admin" and normalized_role != "admin" and self.db.count_admin_users() <= 1:
            raise ValueError("Impossible de rétrograder le dernier administrateur.")

        self.db.update_user(user_id, normalized_username, normalized_role, is_active=is_active)
        return self.db.get_user_by_id(user_id, include_password_hash=False)

    def reset_password(self, user_id: int, new_password: str):
        self.db.update_user_password(user_id, hash_password(new_password))

    def delete_user(self, user_id: int):
        user = self.db.get_user_by_id(user_id, include_password_hash=False)
        if not user:
            raise ValueError("Utilisateur introuvable.")
        if str(user.get("role") or "").lower() == "admin" and self.db.count_admin_users() <= 1:
            raise ValueError("Impossible de supprimer le dernier administrateur.")
        self.db.delete_user(user_id)

    def close(self):
        self.db.close()