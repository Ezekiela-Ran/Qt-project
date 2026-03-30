STEP TO LAUNCH THE PROGRAM:

    pip install -r requirements.txt

    Run the program with python main.py

BUILD WINDOWS EXECUTABLE:

    python -m PyInstaller --noconfirm fac.spec


AUTHENTICATION AND SESSIONS:

At startup, the application now requires authentication for both administrators and standard users.

Behavior:

- On first launch, if no administrator exists, the software asks you to create the first admin account.
- On normal launches, the login dialog is displayed before access to the application.
- The Fichier menu now contains a Déconnexion action.
- Déconnexion returns to the login screen without closing the application.
- Administrative menus are visible only for authenticated administrators.

Notes:

- User accounts are stored in the application database.
- A standard user can use the invoicing features but cannot access administration menus.
- If the active database configuration is changed, disconnect and reconnect so new database connections use the updated settings.


DATABASE CONFIGURATION:

The application is intended to run on a shared MySQL database so that every PC uses the same administrators, users and business data.

At first launch, if no explicit MySQL configuration is present, the software now starts with a local SQLite database automatically. The local database file and all required tables are created by the application itself on first use.

When you open the MySQL configuration screen, the software asks whether the current PC is:

- the server PC
- a client PC

This MySQL configuration screen is now only needed when you want to switch from the default local SQLite mode to a shared MySQL deployment.

Administrators can also edit the database configuration directly from the application:

    Administration > Configuration base de données

This screen allows:

- configuring the PC as the MySQL server
- configuring the PC as a MySQL client
- entering the server IP address on client PCs
- entering a local MySQL administrator account on the server PC for initial bootstrap
- testing the connection before saving
- saving the JSON config file locally on the workstation

Default config file path:

        %LOCALAPPDATA%\FaC\database.json

Default local database path:

    %LOCALAPPDATA%\FaC\fac.db

Legacy LFCA paths are detected automatically on first launch and migrated to the FaC location.

Example config file:

        {
            "engine": "mysql",
            "deployment_role": "client",
            "server_host_hint": "192.168.1.10",
            "mysql": {
                "host": "192.168.1.10",
                "port": 3306,
                "user": "lfca_app",
                "password": "lfca_app",
                "database": "invoicing"
            }
        }

If you explicitly want to use MySQL instead, set:

    DB_ENGINE=mysql

Then the application reads these connection settings from environment variables.
If no variables are set, defaults are:

    DB_HOST=localhost
    DB_PORT=3306
    DB_USER=sam
    DB_PASSWORD=
    DB_NAME=invoicing

Example (Linux/macOS):

    export DB_ENGINE=mysql
    export DB_HOST=localhost
    export DB_PORT=3306
    export DB_USER=your_user
    export DB_PASSWORD=your_password
    export DB_NAME=invoicing
    python main.py

LOCAL NETWORK SHARED DATA (recommended):

For multiple PCs on the same LAN, use a single MySQL server hosted on one machine in the network.
Then configure every PC with the same MySQL connection settings so all PCs share the same admins and users.

Recommended setup:

1. Choose one PC/server in the LAN to host MySQL.
2. Install MySQL Server on that machine and make sure the MySQL service is running.
3. Launch FaC on that machine and choose that this PC is the server.
4. Enter a local MySQL administrator account so FaC can create the shared database and shared application user automatically.
3. On each client PC, either:

     - open the application as an administrator and go to:

         Administration > Configuration base de données

    then choose that this PC is a client and enter only the server IP

     - or manually edit:

             %LOCALAPPDATA%\FaC\database.json

     and set:

             "engine": "mysql"

     with the same host/user/password/database.
5. Start using the application on each PC: all clients will share the same administrators, users and business data in real time.

Example LAN config:

        {
            "engine": "mysql",
            "deployment_role": "client",
            "server_host_hint": "192.168.1.10",
            "mysql": {
                "host": "192.168.1.10",
                "port": 3306,
                "user": "lfca_app",
                "password": "lfca_app",
                "database": "invoicing"
            }
        }

Notes:

- Environment variables still override the JSON file if both are present.
- The config file can also be forced with FAC_DB_CONFIG; the legacy LFCA_DB_CONFIG variable remains accepted for compatibility.
- SQLite local mode is no longer the intended deployment mode for multi-PC use.
- Do not share a SQLite file between PCs on a network folder.
- MySQL is required if you want the same administrators and users on every PC.
- The application now uses explicit transactions for critical multi-step writes to reduce partial saves and counter collisions in multi-user MySQL mode.
- The Ref.b.analyse allocation is serialized for MySQL to avoid duplicate values when several clients work at the same time.
- If the configured MySQL server is unreachable at startup, FaC now fails fast with an explicit startup error instead of appearing frozen for a long TCP timeout.
- MySQL schema creation and migration are now executed only when the shared database actually needs them, instead of on every client startup, to avoid blocking the other PCs on the network.

If your MySQL account does not exist or has no privileges, create/grant it in MySQL:

        CREATE USER 'your_user'@'%' IDENTIFIED BY 'your_password';
        GRANT ALL PRIVILEGES ON *.* TO 'your_user'@'%';
    FLUSH PRIVILEGES;

