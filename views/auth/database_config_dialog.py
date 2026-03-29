from pathlib import Path

from PySide6 import QtWidgets

from models.database.db_config import get_database_settings, save_database_config, test_database_connection


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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = get_database_settings()
        self.config_path = Path(self.settings['config_file'])
        self.setModal(True)
        self.setWindowTitle("Configuration de la base de données")
        self.resize(560, 420)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_values()
        self._toggle_engine_fields()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        intro = QtWidgets.QLabel(
            "Configure la base locale SQLite ou un serveur MySQL distant accessible via l'adresse IP d'un PC ou d'un serveur."
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

        engine_form = QtWidgets.QFormLayout()
        self.engine_input = QtWidgets.QComboBox()
        self.engine_input.addItem("SQLite local", "sqlite")
        self.engine_input.addItem("MySQL distant", "mysql")
        self.engine_input.currentIndexChanged.connect(self._toggle_engine_fields)
        engine_form.addRow("Moteur:", self.engine_input)
        layout.addLayout(engine_form)

        self.sqlite_group = QtWidgets.QGroupBox("Configuration SQLite")
        sqlite_form = QtWidgets.QFormLayout(self.sqlite_group)
        self.sqlite_path_input = QtWidgets.QLineEdit()
        sqlite_form.addRow("Chemin du fichier:", self.sqlite_path_input)
        layout.addWidget(self.sqlite_group)

        self.mysql_group = QtWidgets.QGroupBox("Configuration MySQL")
        mysql_form = QtWidgets.QFormLayout(self.mysql_group)
        self.host_input = QtWidgets.QLineEdit()
        self.port_input = QtWidgets.QSpinBox()
        self.port_input.setRange(1, 65535)
        self.username_input = QtWidgets.QLineEdit()
        self.password_input = QtWidgets.QLineEdit()
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.database_input = QtWidgets.QLineEdit()
        mysql_form.addRow("Adresse IP / Hôte:", self.host_input)
        mysql_form.addRow("Port:", self.port_input)
        mysql_form.addRow("Utilisateur:", self.username_input)
        mysql_form.addRow("Mot de passe:", self.password_input)
        mysql_form.addRow("Base de données:", self.database_input)
        layout.addWidget(self.mysql_group)

        buttons = QtWidgets.QDialogButtonBox()
        self.test_button = buttons.addButton("Tester la connexion", QtWidgets.QDialogButtonBox.ActionRole)
        self.save_button = buttons.addButton("Enregistrer", QtWidgets.QDialogButtonBox.AcceptRole)
        self.close_button = buttons.addButton("Fermer", QtWidgets.QDialogButtonBox.RejectRole)
        self.test_button.clicked.connect(self._test_connection)
        self.save_button.clicked.connect(self._save)
        self.close_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _load_values(self):
        engine_index = max(0, self.engine_input.findData(self.settings['engine']))
        self.engine_input.setCurrentIndex(engine_index)
        self.sqlite_path_input.setText(self.settings['sqlite_path'])
        self.host_input.setText(self.settings['mysql']['host'])
        self.port_input.setValue(int(self.settings['mysql']['port']))
        self.username_input.setText(self.settings['mysql']['user'])
        self.password_input.setText(self.settings['mysql']['password'])
        self.database_input.setText(self.settings['mysql']['database'])
        self.path_label.setText(f"Fichier de configuration: {self.config_path}")

    def _toggle_engine_fields(self):
        engine = self.engine_input.currentData()
        self.sqlite_group.setVisible(engine == 'sqlite')
        self.mysql_group.setVisible(engine == 'mysql')

    def _collect_config(self) -> dict:
        return {
            'engine': self.engine_input.currentData(),
            'sqlite_path': self.sqlite_path_input.text().strip(),
            'mysql': {
                'host': self.host_input.text().strip(),
                'port': self.port_input.value(),
                'user': self.username_input.text().strip(),
                'password': self.password_input.text(),
                'database': self.database_input.text().strip(),
            },
        }

    def _validate(self, config: dict) -> bool:
        if config['engine'] == 'sqlite':
            if not config['sqlite_path']:
                QtWidgets.QMessageBox.warning(self, "Configuration invalide", "Le chemin du fichier SQLite est obligatoire.")
                self.sqlite_path_input.setFocus()
                return False
            return True

        missing_fields = []
        if not config['mysql']['host']:
            missing_fields.append("Adresse IP / Hôte")
        if not config['mysql']['user']:
            missing_fields.append("Utilisateur")
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
            test_database_connection(config)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Connexion impossible", f"Le test a échoué : {exc}")
            return
        QtWidgets.QMessageBox.information(self, "Connexion réussie", "La connexion à la base de données est valide.")

    def _save(self):
        config = self._collect_config()
        if not self._validate(config):
            return
        try:
            save_database_config(config, self.config_path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Enregistrement impossible", f"La configuration n'a pas pu être enregistrée : {exc}")
            return

        QtWidgets.QMessageBox.information(
            self,
            "Configuration enregistrée",
            "La configuration a été enregistrée. Déconnectez-vous puis reconnectez-vous pour ouvrir de nouvelles connexions avec ces paramètres.",
        )
        self.accept()