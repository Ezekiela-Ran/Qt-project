class GlobalVariable:
    invoice_type = ""
    current_user = None

    @classmethod
    def set_current_user(cls, user):
        cls.current_user = user

    @classmethod
    def clear_current_user(cls):
        cls.current_user = None

    @classmethod
    def current_username(cls):
        if not cls.current_user:
            return ""
        return str(cls.current_user.get("username") or "")

    @classmethod
    def is_admin(cls):
        if not cls.current_user:
            return False
        return str(cls.current_user.get("role") or "").lower() == "admin"