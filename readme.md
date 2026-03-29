STEP TO LAUNCH THE PROGRAM:

    pip install -r requirements.txt

    Run the program with python main.py


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

By default, the application uses a local SQLite database file and starts without MySQL.

The application now also reads database settings from a JSON config file, which makes LAN deployment easier on packaged executables.

Administrators can also edit the database configuration directly from the application:

    Administration > Configuration base de données

This screen allows:

- switching between SQLite and MySQL
- entering the server IP address or host name
- entering port, user, password and database name
- testing the connection before saving
- saving the JSON config file locally on the workstation

Default config file path:

        %LOCALAPPDATA%\LFCA\database.json

Default local database path:

    %LOCALAPPDATA%\LFCA\lfca.db

Example config file:

        {
            "engine": "sqlite",
            "sqlite_path": "%LOCALAPPDATA%\\LFCA\\lfca.db",
            "mysql": {
                "host": "192.168.1.10",
                "port": 3306,
                "user": "lfca_user",
                "password": "your_password",
                "database": "invoicing"
            }
        }

Optional environment variables for local mode:

    DB_ENGINE=sqlite
    DB_PATH=C:\path\to\lfca.db

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
Then configure every PC with the same MySQL connection settings.

Recommended setup:

1. Choose one PC/server in the LAN to host MySQL.
2. Open MySQL access on the LAN and create a dedicated application user.
3. On each client PC, either:

     - open the application as an administrator and go to:

         Administration > Configuration base de données

       then save the MySQL server IP, credentials and database name

     - or manually edit:

             %LOCALAPPDATA%\LFCA\database.json

     and set:

             "engine": "mysql"

     with the same host/user/password/database.
4. Disconnect and reconnect the application on each PC after saving the configuration.
5. Start using the application on each PC: all clients will share the same data in real time.

Example LAN config:

        {
            "engine": "mysql",
            "sqlite_path": "%LOCALAPPDATA%\\LFCA\\lfca.db",
            "mysql": {
                "host": "192.168.1.10",
                "port": 3306,
                "user": "lfca_user",
                "password": "your_password",
                "database": "invoicing"
            }
        }

Notes:

- Environment variables still override the JSON file if both are present.
- A shared SQLite file on a network folder is not recommended for concurrent multi-PC use.
- MySQL is the safe option for simultaneous access from several PCs.
- The application now uses explicit transactions for critical multi-step writes to reduce partial saves and counter collisions in multi-user MySQL mode.
- The Ref.b.analyse allocation is serialized for MySQL to avoid duplicate values when several clients work at the same time.

If your MySQL account does not exist or has no privileges, create/grant it in MySQL:

        CREATE USER 'your_user'@'%' IDENTIFIED BY 'your_password';
        GRANT ALL PRIVILEGES ON *.* TO 'your_user'@'%';
    FLUSH PRIVILEGES;

