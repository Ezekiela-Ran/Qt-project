from pathlib import Path
import socket

from PySide6 import QtWidgets

from models.database.db_config import (
    build_client_database_config,
    build_host_database_config,
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
        self.host_name = socket.gethostname()
        self.setModal(True)
        self.setWindowTitle("Configuration SQLite")
        self.setStyleSheet(_DIALOG_STYLE)
        self._build_ui()
        self._load_values()
        self._toggle_role_fields()
        self._apply_initial_size()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        intro = QtWidgets.QLabel(
            "Choisis si ce poste partage la base SQLite ou s'il utilise une base déjà partagée depuis un autre PC. Tous les utilisateurs, administrateurs et documents seront communs tant que tous les postes pointent vers le même fichier SQLite."
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
        self.role_input.addItem("Ce PC partage la base", "host")
        self.role_input.addItem("Ce PC utilise une base partagée", "client")
        self.role_input.currentIndexChanged.connect(self._toggle_role_fields)
        role_form.addRow("Rôle de ce poste:", self.role_input)
        layout.addLayout(role_form)

        self.host_group = QtWidgets.QGroupBox("Configuration du PC qui partage la base")
        host_form = QtWidgets.QFormLayout(self.host_group)
        self.host_database_input = QtWidgets.QLineEdit()
        self.host_database_browse_button = QtWidgets.QPushButton("Parcourir")
        self.host_database_browse_button.clicked.connect(self._browse_host_database_path)
        host_path_layout = QtWidgets.QHBoxLayout()
        host_path_layout.addWidget(self.host_database_input)
        host_path_layout.addWidget(self.host_database_browse_button)
        self.server_ip_label = QtWidgets.QLabel()
        self.server_ip_label.setWordWrap(True)
        self.host_name_label = QtWidgets.QLabel(self.host_name)
        self.share_help_label = QtWidgets.QLabel()
        self.share_help_label.setWordWrap(True)
        host_form.addRow("Nom du PC:", self.host_name_label)
        host_form.addRow("Fichier SQLite local:", host_path_layout)
        host_form.addRow("IP à communiquer aux clients:", self.server_ip_label)
        host_form.addRow("Partage Windows à créer:", self.share_help_label)
        layout.addWidget(self.host_group)

        self.client_group = QtWidgets.QGroupBox("Configuration du PC client")
        client_form = QtWidgets.QFormLayout(self.client_group)
        self.client_database_input = QtWidgets.QLineEdit()
        self.client_database_browse_button = QtWidgets.QPushButton("Parcourir")
        self.client_database_browse_button.clicked.connect(self._browse_client_database_path)
        client_path_layout = QtWidgets.QHBoxLayout()
        client_path_layout.addWidget(self.client_database_input)
        client_path_layout.addWidget(self.client_database_browse_button)
        self.client_example_label = QtWidgets.QLabel(
            "Exemple: \\\\PC-HOTE\\FacCP\\faccp.db"
        )
        self.client_example_label.setWordWrap(True)
        client_form.addRow("Fichier SQLite partagé:", client_path_layout)
        client_form.addRow("Exemple de chemin réseau:", self.client_example_label)
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
        role = self.settings.get('deployment_role') or 'host'
        role_index = max(0, self.role_input.findData(role))
        self.role_input.setCurrentIndex(role_index)
        self.server_ip_label.setText(", ".join(self.detected_ips))
        self.host_database_input.setText(self.settings['sqlite_path'])
        self.client_database_input.setText(self.settings['shared_database_path'])
        host_folder = Path(self.host_database_input.text().strip() or self.settings['sqlite_path']).parent
        self.share_help_label.setText(
            f"Partage le dossier {host_folder} sur Windows, puis donne le chemin réseau complet du fichier .db aux autres postes."
        )
        self.path_label.setText(f"Fichier de configuration: {self.config_path}")

    def _toggle_role_fields(self):
        role = self.role_input.currentData()
        self.host_group.setVisible(role == 'host')
        self.client_group.setVisible(role == 'client')

    def _browse_host_database_path(self):
        initial_path = self.host_database_input.text().strip() or self.settings['sqlite_path']
        selected_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Choisir le fichier SQLite local",
            initial_path,
            "Base SQLite (*.db);;Tous les fichiers (*)",
        )
        if not selected_path:
            return
        if not selected_path.lower().endswith('.db'):
            selected_path += '.db'
        self.host_database_input.setText(selected_path)
        self.share_help_label.setText(
            f"Partage le dossier {Path(selected_path).parent} sur Windows, puis donne le chemin réseau complet du fichier .db aux autres postes."
        )

    def _browse_client_database_path(self):
        initial_path = self.client_database_input.text().strip() or self.settings.get('shared_database_path') or self.settings['sqlite_path']
        selected_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Choisir le fichier SQLite partagé",
            initial_path,
            "Base SQLite (*.db);;Tous les fichiers (*)",
        )
        if selected_path:
            self.client_database_input.setText(selected_path)

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
        host_ip = self.detected_ips[0] if self.detected_ips else '127.0.0.1'
        if role == 'host':
            return build_host_database_config(
                self.host_database_input.text().strip(),
                host_display_name=self.host_name,
                host_ip_hint=host_ip,
            )

        return build_client_database_config(self.client_database_input.text().strip())

    def _validate(self, config: dict) -> bool:
        missing_fields = []
        if self.role_input.currentData() == 'host' and not config['sqlite_path']:
            missing_fields.append("Fichier SQLite local")
        if self.role_input.currentData() == 'client' and not config['sqlite_path']:
            missing_fields.append("Fichier SQLite partagé")
        if missing_fields:
            QtWidgets.QMessageBox.warning(
                self,
                "Configuration invalide",
                "Champs obligatoires manquants: " + ", ".join(missing_fields),
            )
            return False
        database_path = Path(config['sqlite_path'])
        if self.role_input.currentData() == 'host' and database_path.suffix.lower() != '.db':
            QtWidgets.QMessageBox.warning(self, "Configuration invalide", "Le fichier SQLite du poste hôte doit avoir l'extension .db.")
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
        if self.role_input.currentData() == 'host':
            share_folder = Path(config['sqlite_path']).parent
            server_ip = self.detected_ips[0] if self.detected_ips else '127.0.0.1'
            QtWidgets.QMessageBox.information(
                self,
                "Poste hôte prêt",
                f"La base SQLite est prête dans {config['sqlite_path']}. Partage le dossier {share_folder} et communique l'IP {server_ip} ainsi que le chemin réseau complet du fichier .db aux clients.",
            )
            return
        QtWidgets.QMessageBox.information(self, "Connexion réussie", "La connexion au fichier SQLite partagé est valide.")

    def _save(self):
        config = self._collect_config()
        if not self._validate(config):
            return
        try:
            test_database_connection(config)
            save_database_config(config, self.config_path)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Enregistrement impossible", f"La configuration n'a pas pu être enregistrée : {exc}")
            return

        if self.role_input.currentData() == 'host':
            server_ip = self.detected_ips[0] if self.detected_ips else '127.0.0.1'
            share_folder = Path(config['sqlite_path']).parent
            message = (
                "Ce poste est maintenant configuré comme poste hôte. "
                f"Partage le dossier {share_folder} sur Windows, puis configure les autres postes avec l'IP {server_ip} et le chemin réseau complet du fichier {Path(config['sqlite_path']).name}."
            )
        else:
            message = "Ce poste est maintenant configuré comme client SQLite. Les administrateurs, utilisateurs et données seront partagés avec le poste hôte."
        if not self.first_run:
            message += " Déconnectez-vous puis reconnectez-vous pour recharger les connexions."

        QtWidgets.QMessageBox.information(self, "Configuration enregistrée", message)
        self.accept()