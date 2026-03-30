from pathlib import Path

from PySide6 import QtWidgets

from models.database.db_config import (
    DEFAULT_DB_NAME,
    DEFAULT_DB_PORT,
    DEFAULT_DB_USER,
    bootstrap_mysql_server,
    build_client_database_config,
    build_server_database_config,
    detect_local_ipv4_addresses,
    get_database_settings,
    save_database_config,
    test_database_connection,
)


_DIALOG_STYLE = """
QDialog {
    background-color: #1E1E1E;
}

QLabel {
    color: white;
}

QGroupBox {
    color: white;
    border: 1px solid #444444;
    margin-top: 12px;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QLineEdit, QComboBox, QSpinBox {
    background-color: #232323;
    color: white;
    border: 1px solid #444444;
    padding: 6px;
}

QComboBox#roleInput {
    background-color: #FFFFFF;
    color: #000000;
    border: 1px solid #999999;
}

QComboBox#roleInput QAbstractItemView {
    background-color: #FFFFFF;
    color: #000000;
    selection-background-color: #D9EAF7;
    selection-color: #000000;
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


class DatabaseConfigDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, *, first_run: bool = False):
        super().__init__(parent)
        self.first_run = first_run
        self.settings = get_database_settings()
        self.config_path = Path(self.settings['config_file'])
        self.detected_ips = detect_local_ipv4_addresses()
        self.setModal(True)
        self.setWindowTitle("Configuration MySQL")
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_values()
        self._toggle_role_fields()
        self._apply_initial_size()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        intro = QtWidgets.QLabel(
            "Choisis si ce poste héberge la base MySQL ou s'il se connecte au PC serveur. Tous les utilisateurs et administrateurs seront identiques sur chaque poste uniquement si tous les PC utilisent cette même base MySQL."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.path_label = QtWidgets.QLabel()
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        if self.settings['env_overrides']:
            override_keys = ", ".join(sorted(self.settings['env_overrides']))
            warning = QtWidgets.QLabel(
                f"Variables d'environnement actives: {override_keys}. Elles restent prioritaires sur le fichier JSON."
            )
            warning.setWordWrap(True)
            layout.addWidget(warning)

        role_form = QtWidgets.QFormLayout()
        self.role_input = QtWidgets.QComboBox()
        self.role_input.setObjectName("roleInput")
        self.role_input.addItem("Ce PC est le serveur", "server")
        self.role_input.addItem("Ce PC est un client", "client")
        self.role_input.currentIndexChanged.connect(self._toggle_role_fields)
        role_form.addRow("Rôle de ce poste:", self.role_input)
        layout.addLayout(role_form)

        self.server_group = QtWidgets.QGroupBox("Configuration du PC serveur")
        server_form = QtWidgets.QFormLayout(self.server_group)
        self.server_ip_label = QtWidgets.QLabel()
        self.server_ip_label.setWordWrap(True)
        self.mysql_admin_user_input = QtWidgets.QLineEdit("root")
        self.mysql_admin_password_input = QtWidgets.QLineEdit()
        self.mysql_admin_password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.port_input = QtWidgets.QSpinBox()
        self.port_input.setRange(1, 65535)
        self.database_input = QtWidgets.QLineEdit()
        self.app_user_label = QtWidgets.QLabel(DEFAULT_DB_USER)
        self.app_password_label = QtWidgets.QLabel("Compte applicatif partagé automatiquement avec les clients")
        server_form.addRow("IP locale à communiquer aux clients:", self.server_ip_label)
        server_form.addRow("Compte admin MySQL existant:", self.mysql_admin_user_input)
        server_form.addRow("Mot de passe admin MySQL:", self.mysql_admin_password_input)
        server_form.addRow("Port MySQL:", self.port_input)
        server_form.addRow("Base de données:", self.database_input)
        server_form.addRow("Compte applicatif partagé:", self.app_user_label)
        server_form.addRow("Note:", self.app_password_label)
        layout.addWidget(self.server_group)

        self.client_group = QtWidgets.QGroupBox("Configuration du PC client")
        client_form = QtWidgets.QFormLayout(self.client_group)
        self.host_input = QtWidgets.QLineEdit()
        self.client_port_input = QtWidgets.QSpinBox()
        self.client_port_input.setRange(1, 65535)
        self.client_database_label = QtWidgets.QLabel(DEFAULT_DB_NAME)
        self.client_user_label = QtWidgets.QLabel(DEFAULT_DB_USER)
        client_form.addRow("IP du PC serveur:", self.host_input)
        client_form.addRow("Port MySQL:", self.client_port_input)
        client_form.addRow("Base partagée:", self.client_database_label)
        client_form.addRow("Compte applicatif partagé:", self.client_user_label)
        layout.addWidget(self.client_group)

        buttons = QtWidgets.QDialogButtonBox()
        self.test_button = buttons.addButton("Tester la connexion", QtWidgets.QDialogButtonBox.ActionRole)
        self.save_button = buttons.addButton("Configurer", QtWidgets.QDialogButtonBox.AcceptRole)
        close_label = "Quitter" if self.first_run else "Fermer"
        self.close_button = buttons.addButton(close_label, QtWidgets.QDialogButtonBox.RejectRole)
        self.test_button.clicked.connect(self._test_connection)
        self.save_button.clicked.connect(self._save)
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _load_values(self):
        role = self.settings.get('deployment_role') or 'client'
        role_index = max(0, self.role_input.findData(role))
        self.role_input.setCurrentIndex(role_index)
        self.server_ip_label.setText(", ".join(self.detected_ips))
        self.host_input.setText(self.settings['server_host_hint'] or self.settings['mysql']['host'])
        self.port_input.setValue(int(self.settings['mysql']['port']))
        self.database_input.setText(self.settings['mysql']['database'])
        self.client_port_input.setValue(int(self.settings['mysql']['port']))
        self.client_database_label.setText(self.settings['mysql']['database'])
        self.client_user_label.setText(DEFAULT_DB_USER)
        self.path_label.setText(f"Fichier de configuration: {self.config_path}")

    def _toggle_role_fields(self):
        role = self.role_input.currentData()
        self.server_group.setVisible(role == 'server')
        self.client_group.setVisible(role == 'client')

    def _apply_initial_size(self):
        size_hint = self.sizeHint().expandedTo(self.minimumSizeHint())
        target_width = max(640, size_hint.width())
        target_height = max(500, size_hint.height())

        screen = self.screen() or QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            target_width = min(target_width, max(560, int(available.width() * 0.9)))
            target_height = min(target_height, max(420, int(available.height() * 0.9)))

        self.resize(target_width, target_height)

    def _collect_config(self) -> dict:
        role = self.role_input.currentData()
        database_name = self.database_input.text().strip() or DEFAULT_DB_NAME
        if role == 'server':
            server_ip = self.detected_ips[0] if self.detected_ips else '127.0.0.1'
            return build_server_database_config(server_ip=server_ip, database=database_name, port=self.port_input.value())

        return build_client_database_config(server_ip=self.host_input.text().strip(), database=database_name, port=self.client_port_input.value())

    def _validate(self, config: dict) -> bool:
        missing_fields = []
        if self.role_input.currentData() == 'server' and not self.mysql_admin_user_input.text().strip():
            missing_fields.append("Compte admin MySQL")
        if self.role_input.currentData() == 'client' and not config['mysql']['host']:
            missing_fields.append("IP du PC serveur")
        if not config['mysql']['database']:
            missing_fields.append("Base de données")
        if missing_fields:
            QtWidgets.QMessageBox.warning(
                self,
                "Configuration invalide",
                "Champs MySQL obligatoires manquants: " + ", ".join(missing_fields),
            )
            return False
        return True

    def _test_connection(self):
        config = self._collect_config()
        if not self._validate(config):
            return
        try:
            if self.role_input.currentData() == 'server':
                bootstrap_mysql_server(
                    self.mysql_admin_user_input.text().strip(),
                    self.mysql_admin_password_input.text(),
                    database=config['mysql']['database'],
                    port=config['mysql']['port'],
                )
            test_database_connection(config)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Connexion impossible", f"Le test a échoué : {exc}")
            return
        if self.role_input.currentData() == 'server':
            server_ip = self.detected_ips[0] if self.detected_ips else '127.0.0.1'
            QtWidgets.QMessageBox.information(self, "Serveur prêt", f"Le serveur MySQL est prêt. Communique cette IP aux clients: {server_ip}")
            return
        QtWidgets.QMessageBox.information(self, "Connexion réussie", "La connexion au serveur MySQL est valide.")

    def _save(self):
        config = self._collect_config()
        if not self._validate(config):
            return
        try:
            if self.role_input.currentData() == 'server':
                bootstrap_mysql_server(
                    self.mysql_admin_user_input.text().strip(),
                    self.mysql_admin_password_input.text(),
                    database=config['mysql']['database'],
                    port=config['mysql']['port'],
                )
            test_database_connection(config)
            save_database_config(config, self.config_path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Enregistrement impossible", f"La configuration n'a pas pu être enregistrée : {exc}")
            return

        if self.role_input.currentData() == 'server':
            server_ip = self.detected_ips[0] if self.detected_ips else '127.0.0.1'
            message = (
                "Ce poste est maintenant configuré comme serveur. "
                f"Configure les autres postes en client avec l'IP {server_ip} pour partager les mêmes administrateurs et utilisateurs."
            )
        else:
            message = "Ce poste est maintenant configuré comme client MySQL. Les administrateurs et utilisateurs seront partagés avec le serveur."
        if not self.first_run:
            message += " Déconnectez-vous puis reconnectez-vous pour recharger les connexions."

        QtWidgets.QMessageBox.information(self, "Configuration enregistrée", message)
        self.accept()