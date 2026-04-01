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

FacCP works with SQLite only.

At first launch, the software asks whether the current PC is:

- the host PC that shares the SQLite database
- a client PC that uses an already shared SQLite database

Administrators can also edit the database configuration directly from the application:

    Administration > Configuration base de données

This screen allows:

- configuring the PC as the SQLite host
- configuring the PC as a SQLite client
- choosing the local .db file on the host PC
- choosing the shared .db file on client PCs
- testing the connection before saving
- saving the JSON config file locally on the workstation

Default config file path:

        %LOCALAPPDATA%\FacCP\database.json

Default host database path:

    C:\Users\Public\Documents\FacCP\faccp.db

Legacy FaC and LFCA SQLite files are detected automatically on first launch and migrated to the FacCP location.

Example config file:

        {
            "engine": "sqlite",
            "deployment_role": "client",
            "setup_completed": true,
            "sqlite_path": "\\\\PC-HOTE\\FacCP\\faccp.db",
            "shared_database_path": "\\\\PC-HOTE\\FacCP\\faccp.db",
            "host_display_name": "PC-HOTE",
            "host_ip_hint": "192.168.1.10"
        }

If you explicitly want to force a SQLite path by environment variable, set:

    DB_PATH=\\PC-HOTE\FacCP\faccp.db

The config file path can also be forced with FACCP_DB_CONFIG.
FAC_DB_CONFIG and LFCA_DB_CONFIG remain accepted for compatibility.

LOCAL NETWORK SHARED DATA (recommended):

For multiple PCs on the same LAN, use one host PC with a shared Windows folder that contains the SQLite file.
Then configure every client PC with the same shared .db file so all PCs use the same administrators, users and business data.

Recommended setup:

1. Choose one PC in the LAN to host the shared SQLite database.
2. Launch FacCP on that machine and choose that this PC shares the database.
3. Let FacCP create the database automatically in C:\Users\Public\Documents\FacCP\faccp.db, or choose another local .db path.
4. Share the folder that contains the .db file on Windows.
5. On each client PC, open FacCP and choose that this PC uses a shared database.
6. Browse to the shared .db file, for example:

        \\PC-HOTE\FacCP\faccp.db

7. Start using the application on each PC: all clients will share the same administrators, users and business data.

Example LAN config:

        {
            "engine": "sqlite",
            "deployment_role": "client",
            "setup_completed": true,
            "sqlite_path": "\\\\PC-HOTE\\FacCP\\faccp.db",
            "shared_database_path": "\\\\PC-HOTE\\FacCP\\faccp.db"
        }

Notes:

- Environment variables still override the JSON file if both are present.
- The host PC keeps the writable SQLite file locally and shares the folder through Windows.
- Client PCs must point to the exact shared .db file, not just the folder.
- If the shared path becomes unavailable at startup, FacCP fails fast with an explicit startup error.
- SQLite over a local Windows network share is the supported multi-PC mode for this application.

