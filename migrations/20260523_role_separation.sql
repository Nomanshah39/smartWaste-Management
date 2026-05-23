PRAGMA foreign_keys = ON;

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

INSERT OR IGNORE INTO zones (name, city, status, route_plan, notes, created_at, updated_at)
SELECT DISTINCT TRIM(zone), '', 'active', '', 'Migrated from existing bin records', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM bins
WHERE COALESCE(TRIM(zone), '') != '';

INSERT OR IGNORE INTO zones (name, city, status, route_plan, notes, created_at, updated_at)
SELECT DISTINCT TRIM(zone), '', 'active', '', 'Migrated from existing user records', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM users
WHERE role IN ('city_head', 'staff')
  AND COALESCE(TRIM(zone), '') != '';

INSERT OR IGNORE INTO zones (name, city, status, route_plan, notes, created_at, updated_at)
SELECT DISTINCT TRIM(zone), '', 'active', '', 'Migrated from existing task records', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM tasks
WHERE COALESCE(TRIM(zone), '') != '';

UPDATE zones
SET city_head_id = (
    SELECT id FROM users WHERE role = 'city_head' LIMIT 1
),
updated_at = CURRENT_TIMESTAMP
WHERE city_head_id IS NULL
  AND (SELECT COUNT(*) FROM users WHERE role = 'city_head') = 1;
