from PySide6 import QtCore, QtWidgets

from services.auth_service import AuthService


_DIALOG_STYLE = """
QDialog {
    background-color: #1E1E1E;
}

QLabel {
    color: white;
}

QTableWidget {
    background-color: #232323;
    color: white;
    gridline-color: #444444;
    border: 1px solid #444444;
}

QHeaderView::section {
    background-color: #2D2D2D;
    color: white;
    border: 1px solid #444444;
    padding: 6px;
}

QPushButton {
    background-color: #2F5A8F;
    color: white;
    padding: 8px 14px;
    border: none;
    border-radius: 4px;
}

QPushButton:hover {
    background-color: #1E3F61;
}
"""


class SetupAdminDialog(QtWidgets.QDialog):
    def __init__(self, auth_service: AuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.created_user = None
        self.setModal(True)
        self.setWindowTitle("Créer le premier administrateur")
        self.setMinimumWidth(420)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Aucun administrateur n'existe encore. Crée le premier compte admin pour démarrer l'application."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QtWidgets.QFormLayout()
        self.username_input = QtWidgets.QLineEdit()
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.confirm_password_input = QtWidgets.QLineEdit()
        self.confirm_password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        form.addRow("Nom d'utilisateur:", self.username_input)
        form.addRow("Mot de passe:", self.password_input)
        form.addRow("Confirmer:", self.confirm_password_input)
        layout.addLayout(form)

        buttons = QtWidgets.QDialogButtonBox()
        self.create_button = buttons.addButton("Créer l'administrateur", QtWidgets.QDialogButtonBox.AcceptRole)
        self.cancel_button = buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.create_button.clicked.connect(self._submit)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()

        if not username:
            QtWidgets.QMessageBox.warning(self, "Champ obligatoire", "Le nom d'utilisateur est obligatoire.")
            self.username_input.setFocus()
            return
        if not password:
            QtWidgets.QMessageBox.warning(self, "Champ obligatoire", "Le mot de passe est obligatoire.")
            self.password_input.setFocus()
            return
        if password != confirm_password:
            QtWidgets.QMessageBox.warning(self, "Mot de passe", "Les mots de passe ne correspondent pas.")
            self.confirm_password_input.setFocus()
            return

        try:
            self.created_user = self.auth_service.create_initial_admin(username, password)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Création impossible", str(exc))
            return

        self.accept()


class LoginDialog(QtWidgets.QDialog):
    def __init__(self, auth_service: AuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.authenticated_user = None
        self.setModal(True)
        self.setWindowTitle("Connexion")
        self.setMinimumWidth(400)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Identifie-toi pour accéder à l'application.")
        title.setWordWrap(True)
        layout.addWidget(title)

        form = QtWidgets.QFormLayout()
        self.username_input = QtWidgets.QLineEdit()
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        form.addRow("Nom d'utilisateur:", self.username_input)
        form.addRow("Mot de passe:", self.password_input)
        layout.addLayout(form)

        buttons = QtWidgets.QDialogButtonBox()
        self.login_button = buttons.addButton("Se connecter", QtWidgets.QDialogButtonBox.AcceptRole)
        self.cancel_button = buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.login_button.clicked.connect(self._submit)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        user = self.auth_service.authenticate(self.username_input.text(), self.password_input.text())
        if not user:
            QtWidgets.QMessageBox.warning(self, "Connexion impossible", "Nom d'utilisateur ou mot de passe invalide.")
            self.password_input.clear()
            self.password_input.setFocus()
            return
        self.authenticated_user = user
        self.accept()


class UserFormDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, *, title: str, username: str = "", role: str = "user", require_password: bool = True):
        super().__init__(parent)
        self.require_password = require_password
        self.setModal(True)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui(username, role)

    def _build_ui(self, username: str, role: str):
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        self.username_input = QtWidgets.QLineEdit(username)
        self.role_input = QtWidgets.QComboBox()
        self.role_input.addItem("Administrateur", "admin")
        self.role_input.addItem("Utilisateur", "user")
        index = max(0, self.role_input.findData(role))
        self.role_input.setCurrentIndex(index)
        form.addRow("Nom d'utilisateur:", self.username_input)
        form.addRow("Rôle:", self.role_input)

        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.confirm_password_input = QtWidgets.QLineEdit()
        self.confirm_password_input.setEchoMode(QtWidgets.QLineEdit.Password)

        if self.require_password:
            form.addRow("Mot de passe:", self.password_input)
            form.addRow("Confirmer:", self.confirm_password_input)

        layout.addLayout(form)

        buttons = QtWidgets.QDialogButtonBox()
        self.save_button = buttons.addButton("Enregistrer", QtWidgets.QDialogButtonBox.AcceptRole)
        self.cancel_button = buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.save_button.clicked.connect(self._submit)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        if not self.username_input.text().strip():
            QtWidgets.QMessageBox.warning(self, "Champ obligatoire", "Le nom d'utilisateur est obligatoire.")
            self.username_input.setFocus()
            return
        if self.require_password:
            if not self.password_input.text():
                QtWidgets.QMessageBox.warning(self, "Champ obligatoire", "Le mot de passe est obligatoire.")
                self.password_input.setFocus()
                return
            if self.password_input.text() != self.confirm_password_input.text():
                QtWidgets.QMessageBox.warning(self, "Mot de passe", "Les mots de passe ne correspondent pas.")
                self.confirm_password_input.setFocus()
                return
        self.accept()

    def values(self):
        return {
            "username": self.username_input.text().strip(),
            "role": self.role_input.currentData(),
            "password": self.password_input.text(),
        }


class PasswordResetDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Réinitialiser le mot de passe")
        self.setMinimumWidth(420)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.confirm_password_input = QtWidgets.QLineEdit()
        self.confirm_password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        form.addRow("Nouveau mot de passe:", self.password_input)
        form.addRow("Confirmer:", self.confirm_password_input)
        layout.addLayout(form)

        buttons = QtWidgets.QDialogButtonBox()
        self.save_button = buttons.addButton("Réinitialiser", QtWidgets.QDialogButtonBox.AcceptRole)
        self.cancel_button = buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.save_button.clicked.connect(self._submit)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _submit(self):
        if not self.password_input.text():
            QtWidgets.QMessageBox.warning(self, "Champ obligatoire", "Le mot de passe est obligatoire.")
            self.password_input.setFocus()
            return
        if self.password_input.text() != self.confirm_password_input.text():
            QtWidgets.QMessageBox.warning(self, "Mot de passe", "Les mots de passe ne correspondent pas.")
            self.confirm_password_input.setFocus()
            return
        self.accept()

    def password(self):
        return self.password_input.text()


class UserManagementDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, current_user=None):
        super().__init__(parent)
        self.current_user = current_user or {}
        self.auth_service = AuthService()
        self.setModal(True)
        self.setWindowTitle("Gestion des utilisateurs")
        self.resize(720, 420)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_users()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Créer, modifier, supprimer ou réinitialiser les mots de passe des utilisateurs.")
        title.setWordWrap(True)
        layout.addWidget(title)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Nom d'utilisateur", "Rôle", "Statut"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        buttons_layout = QtWidgets.QHBoxLayout()
        self.add_button = QtWidgets.QPushButton("Ajouter")
        self.edit_button = QtWidgets.QPushButton("Modifier")
        self.delete_button = QtWidgets.QPushButton("Supprimer")
        self.reset_password_button = QtWidgets.QPushButton("Réinitialiser mot de passe")
        self.close_button = QtWidgets.QPushButton("Fermer")

        for button in (self.add_button, self.edit_button, self.delete_button, self.reset_password_button):
            buttons_layout.addWidget(button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.close_button)
        layout.addLayout(buttons_layout)

        self.add_button.clicked.connect(self._add_user)
        self.edit_button.clicked.connect(self._edit_user)
        self.delete_button.clicked.connect(self._delete_user)
        self.reset_password_button.clicked.connect(self._reset_password)
        self.close_button.clicked.connect(self.accept)

    def _selected_user(self):
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            QtWidgets.QMessageBox.warning(self, "Sélection requise", "Sélectionne un utilisateur.")
            return None
        row = selected_ranges[0].topRow()
        item = self.table.item(row, 0)
        if item is None:
            return None
        return item.data(QtCore.Qt.UserRole)

    def _load_users(self):
        users = self.auth_service.list_users()
        self.table.setRowCount(len(users))
        for row, user in enumerate(users):
            username_item = QtWidgets.QTableWidgetItem(user.get("username") or "")
            username_item.setData(QtCore.Qt.UserRole, user)
            role_item = QtWidgets.QTableWidgetItem("Administrateur" if user.get("role") == "admin" else "Utilisateur")
            status_item = QtWidgets.QTableWidgetItem("Actif" if int(user.get("is_active") or 0) else "Inactif")
            self.table.setItem(row, 0, username_item)
            self.table.setItem(row, 1, role_item)
            self.table.setItem(row, 2, status_item)
        if users:
            self.table.selectRow(0)

    def _add_user(self):
        dialog = UserFormDialog(self, title="Ajouter un utilisateur", require_password=True)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        values = dialog.values()
        try:
            self.auth_service.create_user(values["username"], values["password"], values["role"])
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Création impossible", str(exc))
            return
        self._load_users()

    def _edit_user(self):
        user = self._selected_user()
        if not user:
            return
        if user.get("id") == self.current_user.get("id"):
            QtWidgets.QMessageBox.warning(self, "Modification interdite", "Modifie ce compte après reconnexion avec un autre administrateur.")
            return
        dialog = UserFormDialog(
            self,
            title="Modifier l'utilisateur",
            username=user.get("username") or "",
            role=user.get("role") or "user",
            require_password=False,
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        values = dialog.values()
        try:
            self.auth_service.update_user(user["id"], values["username"], values["role"], is_active=True)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Modification impossible", str(exc))
            return
        self._load_users()

    def _delete_user(self):
        user = self._selected_user()
        if not user:
            return
        if user.get("id") == self.current_user.get("id"):
            QtWidgets.QMessageBox.warning(self, "Suppression interdite", "Impossible de supprimer l'utilisateur connecté.")
            return
        reply = QtWidgets.QMessageBox.question(
            self,
            "Suppression",
            f"Supprimer l'utilisateur {user.get('username')} ?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.auth_service.delete_user(user["id"])
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Suppression impossible", str(exc))
            return
        self._load_users()

    def _reset_password(self):
        user = self._selected_user()
        if not user:
            return
        dialog = PasswordResetDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        try:
            self.auth_service.reset_password(user["id"], dialog.password())
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Réinitialisation impossible", str(exc))
            return
        QtWidgets.QMessageBox.information(self, "Mot de passe", "Le mot de passe a été réinitialisé.")

    def closeEvent(self, event):
        try:
            self.auth_service.close()
        finally:
            super().closeEvent(event)
