from pathlib import Path
import sqlite3


SQLITE_CONNECT_TIMEOUT_SECONDS = 10


class SQLiteCursorWrapper:
    def __init__(self, cursor: sqlite3.Cursor, dictionary: bool = False):
        self._cursor = cursor
        self._dictionary = dictionary

    @staticmethod
    def _translate(query: str) -> str:
        return query.replace("%s", "?")

    def execute(self, query: str, params=None):
        translated = self._translate(query)
        if params is None:
            self._cursor.execute(translated)
        else:
            self._cursor.execute(translated, params)
        return self

    def executemany(self, query: str, seq_of_params):
        self._cursor.executemany(self._translate(query), seq_of_params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if self._dictionary:
            return dict(row)
        return tuple(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._dictionary:
            return [dict(row) for row in rows]
        return [tuple(row) for row in rows]

    def close(self):
        self._cursor.close()

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class SQLiteConnectionWrapper:
    def __init__(self, database_path: Path, *, create_if_missing: bool = True):
        if create_if_missing:
            database_path.parent.mkdir(parents=True, exist_ok=True)
        elif not database_path.exists():
            raise FileNotFoundError(f"Base SQLite introuvable: {database_path}")

        self._conn = sqlite3.connect(str(database_path), timeout=SQLITE_CONNECT_TIMEOUT_SECONDS)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.autocommit = False

    def cursor(self, dictionary: bool = False):
        return SQLiteCursorWrapper(self._conn.cursor(), dictionary=dictionary)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def connect(database_path: Path, *, create_if_missing: bool = True) -> SQLiteConnectionWrapper:
    return SQLiteConnectionWrapper(database_path, create_if_missing=create_if_missing)