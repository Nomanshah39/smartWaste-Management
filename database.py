import sqlite3
from datetime import datetime

from flask import current_app, g
from werkzeug.security import generate_password_hash


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'city_head', 'staff')),
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    city TEXT,
    zone TEXT,
    meta TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    employee_id TEXT,
    shift_name TEXT,
    vehicle TEXT,
    supervisor_name TEXT,
    emergency_contact TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bin_code TEXT NOT NULL UNIQUE,
    location TEXT NOT NULL,
    zone TEXT,
    capacity_liters INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'maintenance', 'offline')),
    level TEXT NOT NULL DEFAULT 'unknown',
    sensor_status TEXT NOT NULL DEFAULT 'unknown',
    assigned_user_id INTEGER,
    last_cleaned TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    zone TEXT,
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'overdue')),
    due_at TEXT,
    assigned_user_id INTEGER,
    bin_id INTEGER,
    created_by_user_id INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (bin_id) REFERENCES bins(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'read', 'resolved')),
    user_id INTEGER,
    bin_id INTEGER,
    created_by_user_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (bin_id) REFERENCES bins(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS validation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bin_id INTEGER,
    created_by_user_id INTEGER,
    location_snapshot TEXT,
    image_name TEXT,
    image_path TEXT,
    sensor_distance_cm REAL,
    sensor_fill_percent REAL,
    sensor_level TEXT,
    sensor_source TEXT,
    sensor_status TEXT,
    ai_level TEXT,
    confidence REAL,
    probabilities_json TEXT,
    match_result TEXT,
    review_status TEXT NOT NULL DEFAULT 'new' CHECK (review_status IN ('new', 'reviewed', 'resolved')),
    review_notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bin_id) REFERENCES bins(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL
);
"""


def utc_now():
    return datetime.utcnow().replace(microsecond=0).isoformat(sep=' ')


def get_db():
    if 'db' not in g:
        connection = sqlite3.connect(current_app.config['DATABASE_PATH'])
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        g.db = connection
    return g.db


def close_db(_exception=None):
    connection = g.pop('db', None)
    if connection is not None:
        connection.close()


def query_all(query, params=()):
    return get_db().execute(query, params).fetchall()


def query_one(query, params=()):
    return get_db().execute(query, params).fetchone()


def execute(query, params=()):
    connection = get_db()
    cursor = connection.execute(query, params)
    connection.commit()
    return cursor


def init_database():
    connection = sqlite3.connect(current_app.config['DATABASE_PATH'])
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    connection.executescript(SCHEMA)
    connection.execute("DROP TABLE IF EXISTS reports")

    admin_exists = connection.execute(
        "SELECT id FROM users WHERE username = ?",
        (current_app.config['DEFAULT_ADMIN_USERNAME'],),
    ).fetchone()

    if admin_exists is None:
        now = utc_now()
        connection.execute(
            """
            INSERT INTO users (
                username, password_hash, role, full_name, email, city, zone, meta, status,
                created_at, updated_at
            ) VALUES (?, ?, 'admin', ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                current_app.config['DEFAULT_ADMIN_USERNAME'],
                generate_password_hash(current_app.config['DEFAULT_ADMIN_PASSWORD']),
                'System Administrator',
                'admin@smartwaste.local',
                'Smart City',
                'HQ',
                'Default admin created automatically',
                now,
                now,
            ),
        )

    connection.commit()
    connection.close()


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_database()
