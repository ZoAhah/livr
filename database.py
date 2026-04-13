import sqlite3

DATABASE = 'livraison.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    # Utilisateurs (restaurants)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            restaurant     TEXT    NOT NULL,
            email          TEXT    NOT NULL UNIQUE,
            password       TEXT    NOT NULL,
            plan           TEXT    NOT NULL DEFAULT 'trial',
            trial_ends_at  TEXT    NOT NULL DEFAULT (datetime('now', '+14 days', 'localtime')),
            created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    # Livreurs
    conn.execute('''
        CREATE TABLE IF NOT EXISTS drivers (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name    TEXT    NOT NULL,
            vehicle TEXT    NOT NULL,
            status  TEXT    NOT NULL DEFAULT 'disponible',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Commandes
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            client     TEXT    NOT NULL,
            address    TEXT    NOT NULL,
            phone      TEXT    NOT NULL,
            amount     REAL    NOT NULL,
            payment    TEXT    NOT NULL DEFAULT 'espèces',
            status     TEXT    NOT NULL DEFAULT 'préparation',
            driver_id  INTEGER,
            created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id)   REFERENCES users(id),
            FOREIGN KEY (driver_id) REFERENCES drivers(id)
        )
    ''')

    # Messages de contact
    conn.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            email      TEXT NOT NULL,
            message    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    ''')

    conn.commit()
    conn.close()
