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
    bin_height_cm REAL DEFAULT 30,
    bin_width_cm REAL DEFAULT 0,
    low_threshold_cm REAL DEFAULT 20,
    medium_threshold_cm REAL DEFAULT 10,
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

CREATE TABLE IF NOT EXISTS zones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    city TEXT,
    city_head_id INTEGER,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    route_plan TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (city_head_id) REFERENCES users(id) ON DELETE SET NULL
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
    ensure_bin_columns(connection)
    ensure_zone_table(connection)
    seed_zones_from_existing_data(connection)
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


def ensure_bin_columns(connection):
    columns = {row['name'] for row in connection.execute("PRAGMA table_info(bins)").fetchall()}
    additions = {
        'bin_height_cm': "ALTER TABLE bins ADD COLUMN bin_height_cm REAL DEFAULT 30",
        'bin_width_cm': "ALTER TABLE bins ADD COLUMN bin_width_cm REAL DEFAULT 0",
        'low_threshold_cm': "ALTER TABLE bins ADD COLUMN low_threshold_cm REAL DEFAULT 20",
        'medium_threshold_cm': "ALTER TABLE bins ADD COLUMN medium_threshold_cm REAL DEFAULT 10",
    }
    for name, statement in additions.items():
        if name not in columns:
            connection.execute(statement)


def ensure_zone_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            city TEXT,
            city_head_id INTEGER,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
            route_plan TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (city_head_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    columns = {row['name'] for row in connection.execute("PRAGMA table_info(zones)").fetchall()}
    additions = {
        'city': "ALTER TABLE zones ADD COLUMN city TEXT",
        'city_head_id': "ALTER TABLE zones ADD COLUMN city_head_id INTEGER REFERENCES users(id) ON DELETE SET NULL",
        'status': "ALTER TABLE zones ADD COLUMN status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive'))",
        'route_plan': "ALTER TABLE zones ADD COLUMN route_plan TEXT",
        'notes': "ALTER TABLE zones ADD COLUMN notes TEXT",
        'created_at': "ALTER TABLE zones ADD COLUMN created_at TEXT",
        'updated_at': "ALTER TABLE zones ADD COLUMN updated_at TEXT",
    }
    for name, statement in additions.items():
        if name not in columns:
            connection.execute(statement)


def split_zone_names(value):
    if value is None:
        return []
    names = []
    for token in str(value).replace(';', ',').split(','):
        token = token.strip()
        if token:
            names.append(token)
    return names


def seed_zones_from_existing_data(connection):
    now = utc_now()
    zone_names = set()
    existing_zone_count = connection.execute("SELECT COUNT(*) AS count FROM zones").fetchone()['count']

    for table in ('bins', 'tasks'):
        for row in connection.execute(f"SELECT DISTINCT zone FROM {table} WHERE COALESCE(TRIM(zone), '') != ''").fetchall():
            zone_names.update(split_zone_names(row['zone']))

    for row in connection.execute(
        "SELECT DISTINCT zone FROM users WHERE role IN ('city_head', 'staff') AND COALESCE(TRIM(zone), '') != ''"
    ).fetchall():
        zone_names.update(split_zone_names(row['zone']))

    for name in sorted(zone_names):
        connection.execute(
            """
            INSERT OR IGNORE INTO zones (name, city, status, route_plan, notes, created_at, updated_at)
            VALUES (?, '', 'active', '', 'Migrated from existing zone text fields', ?, ?)
            """,
            (name, now, now),
        )

    city_heads = connection.execute("SELECT id, zone FROM users WHERE role = 'city_head'").fetchall()
    for city_head in city_heads:
        for name in split_zone_names(city_head['zone']):
            connection.execute(
                "UPDATE zones SET city_head_id = ?, updated_at = ? WHERE LOWER(name) = LOWER(?)",
                (city_head['id'], now, name),
            )

    unassigned_count = connection.execute(
        "SELECT COUNT(*) AS count FROM zones WHERE city_head_id IS NULL"
    ).fetchone()['count']
    if existing_zone_count == 0 and len(city_heads) == 1 and unassigned_count > 0:
        connection.execute(
            "UPDATE zones SET city_head_id = ?, updated_at = ? WHERE city_head_id IS NULL",
            (city_heads[0]['id'], now),
        )


def init_app(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_database()
