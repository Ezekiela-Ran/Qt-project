STEP TO LAUNCH THE PROGRAM:

    pip install -r requirements.txt

    Run the program with python main.py


DATABASE CONFIGURATION:

By default, the application uses a local SQLite database file and starts without MySQL.

Default local database path:

    %LOCALAPPDATA%\LFCA\lfca.db

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

If your MySQL account does not exist or has no privileges, create/grant it in MySQL:

    CREATE USER 'your_user'@'localhost' IDENTIFIED BY 'your_password';
    GRANT ALL PRIVILEGES ON *.* TO 'your_user'@'localhost';
    FLUSH PRIVILEGES;

