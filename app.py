import json
import os
import re
import threading
import time
from datetime import datetime
from functools import wraps

import numpy as np
import serial
import tensorflow as tf
from flask import Flask, jsonify, render_template, request, send_from_directory, session, g
from PIL import Image, UnidentifiedImageError
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import (
    BAUD_RATE,
    CLASS_NAMES,
    DATABASE_PATH,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_DEVICE_ID,
    IMG_SIZE,
    MAX_UPLOAD_MB,
    MODEL_PATH,
    SECRET_KEY,
    SENSOR_API_KEY,
    SENSOR_MODE,
    SERIAL_PORT,
    TRAINING_SUMMARY_PATH,
    UPLOAD_DIR,
)
from database import execute, init_app as init_database_app, query_all, query_one, utc_now
from sensor_utils import (
    compare_levels,
    normalize_level_name,
    sensor_distance_to_fill_percent,
    sensor_distance_to_level,
)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
ROLE_OPTIONS = ('admin', 'city_head', 'staff')
STATUS_OPTIONS = ('active', 'inactive')
BIN_STATUS_OPTIONS = ('active', 'maintenance', 'offline')
TASK_PRIORITY_OPTIONS = ('low', 'medium', 'high')
TASK_STATUS_OPTIONS = ('pending', 'in_progress', 'completed', 'overdue')
ALERT_PRIORITY_OPTIONS = ('low', 'medium', 'high')
ALERT_STATUS_OPTIONS = ('open', 'read', 'resolved')
VALIDATION_REVIEW_STATUS_OPTIONS = ('new', 'reviewed', 'resolved')

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.update(
    SECRET_KEY=SECRET_KEY,
    MAX_CONTENT_LENGTH=MAX_UPLOAD_MB * 1024 * 1024,
    DATABASE_PATH=DATABASE_PATH,
    DEFAULT_ADMIN_USERNAME=DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_PASSWORD=DEFAULT_ADMIN_PASSWORD,
)

os.makedirs(UPLOAD_DIR, exist_ok=True)

init_database_app(app)

model = None
serial_connection = None
sensor_lock = threading.Lock()
sensor_worker_started = False


def load_class_names():
    if os.path.exists(TRAINING_SUMMARY_PATH):
        try:
            with open(TRAINING_SUMMARY_PATH, 'r', encoding='utf-8') as handle:
                summary = json.load(handle)
            names = summary.get('class_names')
            if isinstance(names, list) and names:
                return [str(name).strip().lower() for name in names]
        except (OSError, json.JSONDecodeError):
            pass
    return CLASS_NAMES[:]


class_names = load_class_names()
latest_sensor = {
    'device_id': DEFAULT_DEVICE_ID,
    'distance_cm': None,
    'distance_inch': None,
    'fill_percent': None,
    'sensor_level': 'unknown',
    'source': SENSOR_MODE,
    'raw': '',
    'status': '',
    'updated_at': None,
}


def default_sensor_status():
    if SENSOR_MODE == 'serial':
        return f'Waiting for serial sensor on {SERIAL_PORT}'
    if SENSOR_MODE == 'auto':
        return f'Auto mode enabled. Trying serial sensor on {SERIAL_PORT}, otherwise manual/HTTP can still be used.'
    if SENSOR_MODE == 'http':
        return 'Waiting for sensor updates on /api/reading'
    return 'Manual sensor mode. Enter distance in the dashboard or post to /api/reading.'


latest_sensor['status'] = default_sensor_status()


def sanitize_text(value, fallback=''):
    if value is None:
        return fallback
    value = str(value).strip()
    return value if value else fallback


def parse_int(value, fallback=None):
    if value in (None, ''):
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def parse_float(value, fallback=None):
    if value in (None, ''):
        return fallback
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return fallback


def parse_distance_value(value):
    return parse_float(value, fallback=None)


def allowed_image(filename: str) -> bool:
    _, extension = os.path.splitext(filename.lower())
    return extension in ALLOWED_EXTENSIONS


def current_user():
    if hasattr(g, 'current_user'):
        return g.current_user

    user_id = session.get('user_id')
    if user_id is None:
        g.current_user = None
        return None

    g.current_user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return g.current_user


def login_required(view_function):
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        if current_user() is None:
            return jsonify({'error': 'authentication required'}), 401
        return view_function(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def decorator(view_function):
        @wraps(view_function)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({'error': 'authentication required'}), 401
            if user['role'] not in roles:
                return jsonify({'error': 'forbidden'}), 403
            return view_function(*args, **kwargs)

        return wrapper

    return decorator


def row_to_user(row):
    if row is None:
        return None
    return {
        'id': row['id'],
        'username': row['username'],
        'role': row['role'],
        'fullName': row['full_name'],
        'email': row['email'] or '',
        'phone': row['phone'] or '',
        'city': row['city'] or '',
        'zone': row['zone'] or '',
        'meta': row['meta'] or '',
        'status': row['status'],
        'employeeId': row['employee_id'] or '',
        'shiftName': row['shift_name'] or '',
        'vehicle': row['vehicle'] or '',
        'supervisorName': row['supervisor_name'] or '',
        'emergencyContact': row['emergency_contact'] or '',
        'notes': row['notes'] or '',
        'createdAt': row['created_at'],
        'updatedAt': row['updated_at'],
    }


def row_to_bin(row):
    return {
        'id': row['id'],
        'binCode': row['bin_code'],
        'location': row['location'],
        'zone': row['zone'] or '',
        'capacityLiters': row['capacity_liters'] or 0,
        'status': row['status'],
        'level': row['level'],
        'sensorStatus': row['sensor_status'],
        'assignedUserId': row['assigned_user_id'],
        'assignedUserName': row['assigned_user_name'] or '',
        'lastCleaned': row['last_cleaned'] or '',
        'notes': row['notes'] or '',
        'createdAt': row['created_at'],
        'updatedAt': row['updated_at'],
    }


def row_to_task(row):
    return {
        'id': row['id'],
        'title': row['title'],
        'description': row['description'] or '',
        'zone': row['zone'] or '',
        'priority': row['priority'],
        'status': row['status'],
        'dueAt': row['due_at'] or '',
        'assignedUserId': row['assigned_user_id'],
        'assignedUserName': row['assigned_user_name'] or '',
        'binId': row['bin_id'],
        'binCode': row['bin_code'] or '',
        'createdByUserId': row['created_by_user_id'],
        'createdByName': row['created_by_name'] or '',
        'notes': row['notes'] or '',
        'createdAt': row['created_at'],
        'updatedAt': row['updated_at'],
    }


def row_to_alert(row):
    return {
        'id': row['id'],
        'title': row['title'],
        'message': row['message'],
        'priority': row['priority'],
        'status': row['status'],
        'userId': row['user_id'],
        'userName': row['user_name'] or '',
        'binId': row['bin_id'],
        'binCode': row['bin_code'] or '',
        'createdByUserId': row['created_by_user_id'],
        'createdByName': row['created_by_name'] or '',
        'createdAt': row['created_at'],
        'updatedAt': row['updated_at'],
    }


def row_to_validation(row):
    probabilities = {}
    if row['probabilities_json']:
        try:
            probabilities = json.loads(row['probabilities_json'])
        except json.JSONDecodeError:
            probabilities = {}

    return {
        'id': row['id'],
        'binId': row['bin_id'],
        'binCode': row['bin_code'] or '',
        'location': row['location_snapshot'] or '',
        'imageName': row['image_name'] or '',
        'imageUrl': f"/uploads/{row['image_name']}" if row['image_name'] else '',
        'sensorDistanceCm': row['sensor_distance_cm'],
        'sensorFillPercent': row['sensor_fill_percent'],
        'sensorLevel': row['sensor_level'] or 'unknown',
        'sensorSource': row['sensor_source'] or '',
        'sensorStatus': row['sensor_status'] or '',
        'aiLevel': row['ai_level'] or 'unknown',
        'confidence': row['confidence'],
        'probabilities': probabilities,
        'match': row['match_result'] or 'Unavailable',
        'reviewStatus': row['review_status'],
        'reviewNotes': row['review_notes'] or '',
        'createdByUserId': row['created_by_user_id'],
        'createdByName': row['created_by_name'] or '',
        'createdAt': row['created_at'],
        'timestamp': row['created_at'],
        'updatedAt': row['updated_at'],
    }


def json_body():
    return request.get_json(silent=True) or {}


def api_error(message, status=400):
    return jsonify({'error': message}), status


@app.errorhandler(RequestEntityTooLarge)
def handle_request_too_large(_exc):
    if request.path.startswith('/api/'):
        return api_error(f'uploaded file is too large. Maximum allowed size is {MAX_UPLOAD_MB} MB.', 413)
    return _exc


@app.errorhandler(HTTPException)
def handle_http_exception(exc):
    if request.path.startswith('/api/'):
        description = exc.description if isinstance(exc.description, str) else exc.name
        return api_error(description or 'request failed', exc.code or 500)
    return exc


@app.errorhandler(Exception)
def handle_unexpected_exception(exc):
    if request.path.startswith('/api/'):
        app.logger.exception('Unhandled API error: %s', exc)
        return api_error('unexpected server error. Please try again.', 500)
    raise exc


def get_sensor_snapshot():
    with sensor_lock:
        return dict(latest_sensor)


def get_legacy_sensor_snapshot():
    snapshot = get_sensor_snapshot()
    return {
        'cm': snapshot.get('distance_cm'),
        'inch': snapshot.get('distance_inch'),
        'raw': snapshot.get('raw', ''),
        'status': snapshot.get('status', default_sensor_status()),
    }


def update_sensor_snapshot(distance_cm=None, distance_inch=None, raw='', source='manual', device_id=None, status=None):
    distance_cm = parse_distance_value(distance_cm)
    distance_inch = parse_distance_value(distance_inch)

    if distance_cm is None and distance_inch is not None:
        distance_cm = round(distance_inch * 2.54, 2)
    if distance_inch is None and distance_cm is not None:
        distance_inch = round(distance_cm / 2.54, 2)

    sensor_level = sensor_distance_to_level(distance_cm)
    fill_percent = sensor_distance_to_fill_percent(distance_cm)

    with sensor_lock:
        latest_sensor['device_id'] = device_id or latest_sensor['device_id']
        latest_sensor['distance_cm'] = distance_cm
        latest_sensor['distance_inch'] = distance_inch
        latest_sensor['fill_percent'] = fill_percent
        latest_sensor['sensor_level'] = sensor_level
        latest_sensor['source'] = source
        latest_sensor['raw'] = raw
        latest_sensor['status'] = status or f'{source.title()} sensor updated successfully'
        latest_sensor['updated_at'] = datetime.now().isoformat(timespec='seconds')
        return dict(latest_sensor)


def parse_serial_line(line: str):
    cm_match = re.search(r'Distance(?:\s*\(cm\))?\s*[:=]\s*([0-9.]+)', line, flags=re.IGNORECASE)
    inch_match = re.search(r'Distance(?:\s*\(inch\))?\s*[:=]\s*([0-9.]+)', line, flags=re.IGNORECASE)

    if not cm_match:
        fallback_cm_match = re.search(r'([0-9.]+)\s*cm', line, flags=re.IGNORECASE)
        if fallback_cm_match:
            cm_match = fallback_cm_match
    if not inch_match:
        fallback_inch_match = re.search(r'([0-9.]+)\s*(?:inch|inches|in)\b', line, flags=re.IGNORECASE)
        if fallback_inch_match:
            inch_match = fallback_inch_match

    distance_cm = parse_distance_value(cm_match.group(1)) if cm_match else None
    distance_inch = parse_distance_value(inch_match.group(1)) if inch_match else None
    return distance_cm, distance_inch


def connect_serial_forever():
    global serial_connection
    while True:
        try:
            serial_connection = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            update_sensor_snapshot(
                distance_cm=get_sensor_snapshot().get('distance_cm'),
                distance_inch=get_sensor_snapshot().get('distance_inch'),
                raw=get_sensor_snapshot().get('raw', ''),
                source='serial',
                device_id=DEFAULT_DEVICE_ID,
                status=f'Connected to serial sensor on {SERIAL_PORT}',
            )
            print(f'Connected to {SERIAL_PORT}')
            return
        except Exception as exc:  # pragma: no cover
            with sensor_lock:
                latest_sensor['status'] = f'Serial connection failed: {exc}'
                latest_sensor['source'] = 'serial'
            print(f'Serial connection failed on {SERIAL_PORT}: {exc}')
            time.sleep(2)


def read_serial_loop():
    global serial_connection
    connect_serial_forever()

    while True:
        try:
            line = serial_connection.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                time.sleep(0.05)
                continue

            with sensor_lock:
                latest_sensor['raw'] = line

            distance_cm, distance_inch = parse_serial_line(line)
            if distance_cm is None and distance_inch is None:
                continue

            print(f'Received serial line: {line}')
            update_sensor_snapshot(
                distance_cm=distance_cm,
                distance_inch=distance_inch,
                raw=line,
                source='serial',
                device_id=DEFAULT_DEVICE_ID,
                status=f'Latest reading received from {SERIAL_PORT}',
            )
        except Exception as exc:  # pragma: no cover
            with sensor_lock:
                latest_sensor['status'] = f'Serial read error: {exc}'
                latest_sensor['source'] = 'serial'
            print(f'Serial read error on {SERIAL_PORT}: {exc}')
            try:
                if serial_connection and serial_connection.is_open:
                    serial_connection.close()
            except Exception:
                pass
            time.sleep(2)
            connect_serial_forever()


def start_sensor_worker():
    global sensor_worker_started
    if sensor_worker_started:
        return
    if SENSOR_MODE in ('serial', 'auto'):
        sensor_worker_started = True
        thread = threading.Thread(target=read_serial_loop, daemon=True)
        thread.start()


def load_model_once():
    global model
    if model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f'Model not found at {MODEL_PATH}. Train the model first.')
        model = tf.keras.models.load_model(MODEL_PATH, compile=False)
    return model


def preprocess_image(image_path: str):
    image = Image.open(image_path).convert('RGB').resize(IMG_SIZE)
    array = np.asarray(image, dtype=np.float32)
    return np.expand_dims(array, axis=0)


def predict_image_class(image_path: str):
    mdl = load_model_once()
    array = preprocess_image(image_path)
    predictions = mdl.predict(array, verbose=0)[0]
    predicted_index = int(np.argmax(predictions))
    probabilities = {
        class_names[index]: round(float(predictions[index]) * 100, 2)
        for index in range(len(class_names))
    }
    return {
        'ai_level': class_names[predicted_index],
        'confidence': round(float(predictions[predicted_index]) * 100, 2),
        'probabilities': probabilities,
    }


def resolve_sensor_values(form_data):
    manual_distance_cm = parse_distance_value(form_data.get('sensor_distance_cm'))
    manual_level = normalize_level_name(form_data.get('sensor_level'))
    live_sensor = get_sensor_snapshot()

    if manual_distance_cm is not None:
        return {
            'distance_cm': manual_distance_cm,
            'level': sensor_distance_to_level(manual_distance_cm),
            'fill_percent': sensor_distance_to_fill_percent(manual_distance_cm),
            'source': 'manual',
            'status': 'Manual ultrasonic distance entered in the dashboard',
        }

    if manual_level != 'unknown':
        return {
            'distance_cm': None,
            'level': manual_level,
            'fill_percent': None,
            'source': 'manual',
            'status': 'Manual sensor level entered in the dashboard',
        }

    return {
        'distance_cm': live_sensor.get('distance_cm'),
        'level': live_sensor.get('sensor_level', 'unknown'),
        'fill_percent': live_sensor.get('fill_percent'),
        'source': live_sensor.get('source', 'unknown'),
        'status': live_sensor.get('status', default_sensor_status()),
    }


def fetch_bins_for_user(user):
    if user['role'] == 'staff':
        rows = query_all(
            """
            SELECT bins.*, users.full_name AS assigned_user_name
            FROM bins
            LEFT JOIN users ON users.id = bins.assigned_user_id
            WHERE bins.assigned_user_id = ? OR bins.assigned_user_id IS NULL
            ORDER BY bins.id DESC
            """,
            (user['id'],),
        )
    else:
        rows = query_all(
            """
            SELECT bins.*, users.full_name AS assigned_user_name
            FROM bins
            LEFT JOIN users ON users.id = bins.assigned_user_id
            ORDER BY bins.id DESC
            """
        )
    return [row_to_bin(row) for row in rows]


def fetch_tasks_for_user(user):
    if user['role'] == 'staff':
        rows = query_all(
            """
            SELECT tasks.*, assigned.full_name AS assigned_user_name, bins.bin_code AS bin_code,
                   creator.full_name AS created_by_name
            FROM tasks
            LEFT JOIN users AS assigned ON assigned.id = tasks.assigned_user_id
            LEFT JOIN bins ON bins.id = tasks.bin_id
            LEFT JOIN users AS creator ON creator.id = tasks.created_by_user_id
            WHERE tasks.assigned_user_id = ?
            ORDER BY tasks.id DESC
            """,
            (user['id'],),
        )
    else:
        rows = query_all(
            """
            SELECT tasks.*, assigned.full_name AS assigned_user_name, bins.bin_code AS bin_code,
                   creator.full_name AS created_by_name
            FROM tasks
            LEFT JOIN users AS assigned ON assigned.id = tasks.assigned_user_id
            LEFT JOIN bins ON bins.id = tasks.bin_id
            LEFT JOIN users AS creator ON creator.id = tasks.created_by_user_id
            ORDER BY tasks.id DESC
            """
        )
    return [row_to_task(row) for row in rows]


def fetch_alerts_for_user(user):
    if user['role'] == 'staff':
        rows = query_all(
            """
            SELECT alerts.*, users.full_name AS user_name, bins.bin_code AS bin_code,
                   creator.full_name AS created_by_name
            FROM alerts
            LEFT JOIN users ON users.id = alerts.user_id
            LEFT JOIN bins ON bins.id = alerts.bin_id
            LEFT JOIN users AS creator ON creator.id = alerts.created_by_user_id
            WHERE alerts.user_id = ? OR alerts.user_id IS NULL
            ORDER BY alerts.id DESC
            """,
            (user['id'],),
        )
    else:
        rows = query_all(
            """
            SELECT alerts.*, users.full_name AS user_name, bins.bin_code AS bin_code,
                   creator.full_name AS created_by_name
            FROM alerts
            LEFT JOIN users ON users.id = alerts.user_id
            LEFT JOIN bins ON bins.id = alerts.bin_id
            LEFT JOIN users AS creator ON creator.id = alerts.created_by_user_id
            ORDER BY alerts.id DESC
            """
        )
    return [row_to_alert(row) for row in rows]


def fetch_users_for_reports(user):
    if user['role'] == 'admin':
        rows = query_all("SELECT * FROM users ORDER BY id DESC")
    else:
        rows = query_all(
            "SELECT * FROM users WHERE role IN ('city_head', 'staff') ORDER BY id DESC"
        )
    return [row_to_user(row) for row in rows]


def fetch_validations_for_user(user):
    if user['role'] == 'staff':
        rows = query_all(
            """
            SELECT validation_runs.*, bins.bin_code AS bin_code, users.full_name AS created_by_name
            FROM validation_runs
            LEFT JOIN bins ON bins.id = validation_runs.bin_id
            LEFT JOIN users ON users.id = validation_runs.created_by_user_id
            WHERE validation_runs.created_by_user_id = ?
            ORDER BY validation_runs.id DESC
            """,
            (user['id'],),
        )
    else:
        rows = query_all(
            """
            SELECT validation_runs.*, bins.bin_code AS bin_code, users.full_name AS created_by_name
            FROM validation_runs
            LEFT JOIN bins ON bins.id = validation_runs.bin_id
            LEFT JOIN users ON users.id = validation_runs.created_by_user_id
            ORDER BY validation_runs.id DESC
            """
        )
    return [row_to_validation(row) for row in rows]


def dashboard_payload(user):
    bins = fetch_bins_for_user(user)
    tasks = fetch_tasks_for_user(user)
    alerts = fetch_alerts_for_user(user)
    validations = fetch_validations_for_user(user)

    if user['role'] == 'admin':
        users_count = query_one("SELECT COUNT(*) AS count FROM users")['count']
        matches = len([item for item in validations if item['match'] == 'Match'])
        accuracy = round((matches / len(validations)) * 100, 2) if validations else 0
        metrics = [
            {'label': 'Users', 'value': users_count, 'subtext': 'Admins, city heads, and staff'},
            {'label': 'Bins', 'value': len(bins), 'subtext': 'Managed in SQLite'},
            {'label': 'Open Tasks', 'value': len([task for task in tasks if task['status'] != 'completed']), 'subtext': 'Need action'},
            {'label': 'Validation Accuracy', 'value': f'{accuracy:.2f}%', 'subtext': 'AI versus ultrasonic'},
        ]
    elif user['role'] == 'city_head':
        staff_count = query_one("SELECT COUNT(*) AS count FROM users WHERE role = 'staff'")['count']
        metrics = [
            {'label': 'Staff Members', 'value': staff_count, 'subtext': 'Available in the system'},
            {'label': 'Bins', 'value': len(bins), 'subtext': 'Visible to city head'},
            {'label': 'Tasks', 'value': len(tasks), 'subtext': 'Assigned and tracked'},
            {'label': 'Open Alerts', 'value': len([item for item in alerts if item['status'] == 'open']), 'subtext': 'Need attention'},
        ]
    else:
        my_pending = len([task for task in tasks if task['status'] in ('pending', 'in_progress')])
        metrics = [
            {'label': 'My Tasks', 'value': len(tasks), 'subtext': 'Assigned to this staff account'},
            {'label': 'Pending', 'value': my_pending, 'subtext': 'In progress or waiting'},
            {'label': 'My Bins', 'value': len([bin_item for bin_item in bins if bin_item['assignedUserId'] == user['id']]), 'subtext': 'Directly assigned'},
            {'label': 'My Alerts', 'value': len(alerts), 'subtext': 'Targeted notifications'},
        ]

    return {
        'metrics': metrics,
        'recentTasks': tasks[:5],
        'recentAlerts': alerts[:5],
        'recentValidations': validations[:5],
    }


def lookups_payload(user):
    if user['role'] == 'admin':
        users = [row_to_user(row) for row in query_all("SELECT * FROM users ORDER BY full_name")]
    else:
        users = [row_to_user(row) for row in query_all("SELECT * FROM users WHERE role IN ('city_head', 'staff') ORDER BY full_name")]

    bins = fetch_bins_for_user(user if user['role'] == 'staff' else {'role': 'admin', 'id': user['id']})
    return {
        'roles': list(ROLE_OPTIONS),
        'userStatusOptions': list(STATUS_OPTIONS),
        'binStatusOptions': list(BIN_STATUS_OPTIONS),
        'taskPriorityOptions': list(TASK_PRIORITY_OPTIONS),
        'taskStatusOptions': list(TASK_STATUS_OPTIONS),
        'alertPriorityOptions': list(ALERT_PRIORITY_OPTIONS),
        'alertStatusOptions': list(ALERT_STATUS_OPTIONS),
        'validationReviewStatusOptions': list(VALIDATION_REVIEW_STATUS_OPTIONS),
        'users': users,
        'bins': bins,
    }


def generated_reports_payload(user):
    return {
        'users': fetch_users_for_reports(user),
        'bins': fetch_bins_for_user(user),
        'tasks': fetch_tasks_for_user(user),
        'validations': fetch_validations_for_user(user),
    }


def update_bin_from_validation(bin_id, sensor_values):
    if bin_id is None:
        return
    now = utc_now()
    execute(
        """
        UPDATE bins
        SET level = ?, sensor_status = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            sensor_values['level'] or 'unknown',
            sensor_values['status'] or sensor_values['source'] or 'unknown',
            now,
            bin_id,
        ),
    )


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    payload = json_body()
    username = sanitize_text(payload.get('username')).lower()
    password = sanitize_text(payload.get('password'))
    selected_role = sanitize_text(payload.get('role')).lower()

    if not username or not password:
        return jsonify({'error': 'username and password are required'}), 400

    user = query_one("SELECT * FROM users WHERE username = ?", (username,))
    if user is None or not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'invalid username or password'}), 401
    if user['status'] != 'active':
        return jsonify({'error': 'user is inactive'}), 403
    if selected_role and selected_role != user['role']:
        return jsonify({'error': 'selected role does not match the account role'}), 400

    session['user_id'] = user['id']
    return jsonify({'user': row_to_user(user)})


@app.route('/api/auth/me')
def api_me():
    user = current_user()
    if user is None:
        return jsonify({'user': None})
    return jsonify({'user': row_to_user(user)})


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/dashboard')
@login_required
def api_dashboard():
    user = current_user()
    return jsonify(dashboard_payload(user))


@app.route('/api/lookups')
@login_required
def api_lookups():
    return jsonify(lookups_payload(current_user()))


@app.route('/api/profile', methods=['PUT'])
@login_required
def api_profile_update():
    user = current_user()
    payload = json_body()
    now = utc_now()

    execute(
        """
        UPDATE users
        SET full_name = ?, email = ?, phone = ?, city = ?, zone = ?, meta = ?, employee_id = ?,
            shift_name = ?, vehicle = ?, supervisor_name = ?, emergency_contact = ?, notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            sanitize_text(payload.get('fullName'), user['full_name']),
            sanitize_text(payload.get('email'), user['email'] or ''),
            sanitize_text(payload.get('phone'), user['phone'] or ''),
            sanitize_text(payload.get('city'), user['city'] or ''),
            sanitize_text(payload.get('zone'), user['zone'] or ''),
            sanitize_text(payload.get('meta'), user['meta'] or ''),
            sanitize_text(payload.get('employeeId'), user['employee_id'] or ''),
            sanitize_text(payload.get('shiftName'), user['shift_name'] or ''),
            sanitize_text(payload.get('vehicle'), user['vehicle'] or ''),
            sanitize_text(payload.get('supervisorName'), user['supervisor_name'] or ''),
            sanitize_text(payload.get('emergencyContact'), user['emergency_contact'] or ''),
            sanitize_text(payload.get('notes'), user['notes'] or ''),
            now,
            user['id'],
        ),
    )

    password = sanitize_text(payload.get('password'))
    if password:
        execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (generate_password_hash(password), now, user['id']),
        )

    refreshed = query_one("SELECT * FROM users WHERE id = ?", (user['id'],))
    return jsonify({'user': row_to_user(refreshed)})


@app.route('/api/users')
@roles_required('admin')
def api_users_list():
    rows = query_all("SELECT * FROM users ORDER BY id DESC")
    return jsonify([row_to_user(row) for row in rows])


@app.route('/api/users', methods=['POST'])
@roles_required('admin')
def api_users_create():
    payload = json_body()
    username = sanitize_text(payload.get('username')).lower()
    password = sanitize_text(payload.get('password'))
    role = sanitize_text(payload.get('role'), 'staff').lower()
    full_name = sanitize_text(payload.get('fullName'))

    if not username or not password or not full_name:
        return jsonify({'error': 'full name, username, and password are required'}), 400
    if role not in ROLE_OPTIONS:
        return jsonify({'error': 'invalid role'}), 400
    if query_one("SELECT id FROM users WHERE username = ?", (username,)):
        return jsonify({'error': 'username already exists'}), 400

    now = utc_now()
    cursor = execute(
        """
        INSERT INTO users (
            username, password_hash, role, full_name, email, phone, city, zone, meta, status,
            employee_id, shift_name, vehicle, supervisor_name, emergency_contact, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            username,
            generate_password_hash(password),
            role,
            full_name,
            sanitize_text(payload.get('email')),
            sanitize_text(payload.get('phone')),
            sanitize_text(payload.get('city')),
            sanitize_text(payload.get('zone')),
            sanitize_text(payload.get('meta')),
            sanitize_text(payload.get('status'), 'active').lower(),
            sanitize_text(payload.get('employeeId')),
            sanitize_text(payload.get('shiftName')),
            sanitize_text(payload.get('vehicle')),
            sanitize_text(payload.get('supervisorName')),
            sanitize_text(payload.get('emergencyContact')),
            sanitize_text(payload.get('notes')),
            now,
            now,
        ),
    )

    created = query_one("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,))
    return jsonify(row_to_user(created)), 201


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@roles_required('admin')
def api_users_update(user_id):
    payload = json_body()
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if user is None:
        return jsonify({'error': 'user not found'}), 404

    role = sanitize_text(payload.get('role'), user['role']).lower()
    status = sanitize_text(payload.get('status'), user['status']).lower()
    if role not in ROLE_OPTIONS:
        return jsonify({'error': 'invalid role'}), 400
    if status not in STATUS_OPTIONS:
        return jsonify({'error': 'invalid status'}), 400

    username = sanitize_text(payload.get('username'), user['username']).lower()
    duplicate = query_one("SELECT id FROM users WHERE username = ? AND id != ?", (username, user_id))
    if duplicate:
        return jsonify({'error': 'username already exists'}), 400

    now = utc_now()
    execute(
        """
        UPDATE users
        SET username = ?, role = ?, full_name = ?, email = ?, phone = ?, city = ?, zone = ?, meta = ?,
            status = ?, employee_id = ?, shift_name = ?, vehicle = ?, supervisor_name = ?,
            emergency_contact = ?, notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            username,
            role,
            sanitize_text(payload.get('fullName'), user['full_name']),
            sanitize_text(payload.get('email'), user['email'] or ''),
            sanitize_text(payload.get('phone'), user['phone'] or ''),
            sanitize_text(payload.get('city'), user['city'] or ''),
            sanitize_text(payload.get('zone'), user['zone'] or ''),
            sanitize_text(payload.get('meta'), user['meta'] or ''),
            status,
            sanitize_text(payload.get('employeeId'), user['employee_id'] or ''),
            sanitize_text(payload.get('shiftName'), user['shift_name'] or ''),
            sanitize_text(payload.get('vehicle'), user['vehicle'] or ''),
            sanitize_text(payload.get('supervisorName'), user['supervisor_name'] or ''),
            sanitize_text(payload.get('emergencyContact'), user['emergency_contact'] or ''),
            sanitize_text(payload.get('notes'), user['notes'] or ''),
            now,
            user_id,
        ),
    )

    password = sanitize_text(payload.get('password'))
    if password:
        execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (generate_password_hash(password), now, user_id),
        )

    updated = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return jsonify(row_to_user(updated))


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@roles_required('admin')
def api_users_delete(user_id):
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if user is None:
        return jsonify({'error': 'user not found'}), 404
    if user_id == current_user()['id']:
        return jsonify({'error': 'you cannot delete your own account'}), 400
    if user['role'] == 'admin':
        admin_count = query_one("SELECT COUNT(*) AS count FROM users WHERE role = 'admin'")['count']
        if admin_count <= 1:
            return jsonify({'error': 'cannot delete the last admin account'}), 400
    execute("DELETE FROM users WHERE id = ?", (user_id,))
    return jsonify({'success': True})


@app.route('/api/bins')
@login_required
def api_bins_list():
    return jsonify(fetch_bins_for_user(current_user()))


@app.route('/api/bins', methods=['POST'])
@roles_required('admin', 'city_head')
def api_bins_create():
    payload = json_body()
    bin_code = sanitize_text(payload.get('binCode')).upper()
    location = sanitize_text(payload.get('location'))
    status = sanitize_text(payload.get('status'), 'active').lower()

    if not bin_code or not location:
        return jsonify({'error': 'bin code and location are required'}), 400
    if status not in BIN_STATUS_OPTIONS:
        return jsonify({'error': 'invalid bin status'}), 400
    if query_one("SELECT id FROM bins WHERE bin_code = ?", (bin_code,)):
        return jsonify({'error': 'bin code already exists'}), 400

    now = utc_now()
    cursor = execute(
        """
        INSERT INTO bins (
            bin_code, location, zone, capacity_liters, status, level, sensor_status, assigned_user_id,
            last_cleaned, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bin_code,
            location,
            sanitize_text(payload.get('zone')),
            parse_int(payload.get('capacityLiters'), 0),
            status,
            sanitize_text(payload.get('level'), 'unknown').lower(),
            sanitize_text(payload.get('sensorStatus'), 'unknown'),
            parse_int(payload.get('assignedUserId')),
            sanitize_text(payload.get('lastCleaned')),
            sanitize_text(payload.get('notes')),
            now,
            now,
        ),
    )
    row = query_one(
        """
        SELECT bins.*, users.full_name AS assigned_user_name
        FROM bins LEFT JOIN users ON users.id = bins.assigned_user_id
        WHERE bins.id = ?
        """,
        (cursor.lastrowid,),
    )
    return jsonify(row_to_bin(row)), 201


@app.route('/api/bins/<int:bin_id>', methods=['PUT'])
@roles_required('admin', 'city_head')
def api_bins_update(bin_id):
    payload = json_body()
    existing = query_one("SELECT * FROM bins WHERE id = ?", (bin_id,))
    if existing is None:
        return jsonify({'error': 'bin not found'}), 404

    bin_code = sanitize_text(payload.get('binCode'), existing['bin_code']).upper()
    location = sanitize_text(payload.get('location'), existing['location'])
    status = sanitize_text(payload.get('status'), existing['status']).lower()
    if status not in BIN_STATUS_OPTIONS:
        return jsonify({'error': 'invalid bin status'}), 400
    duplicate = query_one("SELECT id FROM bins WHERE bin_code = ? AND id != ?", (bin_code, bin_id))
    if duplicate:
        return jsonify({'error': 'bin code already exists'}), 400

    now = utc_now()
    execute(
        """
        UPDATE bins
        SET bin_code = ?, location = ?, zone = ?, capacity_liters = ?, status = ?, level = ?,
            sensor_status = ?, assigned_user_id = ?, last_cleaned = ?, notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            bin_code,
            location,
            sanitize_text(payload.get('zone'), existing['zone'] or ''),
            parse_int(payload.get('capacityLiters'), existing['capacity_liters'] or 0),
            status,
            sanitize_text(payload.get('level'), existing['level']).lower(),
            sanitize_text(payload.get('sensorStatus'), existing['sensor_status']),
            parse_int(payload.get('assignedUserId'), existing['assigned_user_id']),
            sanitize_text(payload.get('lastCleaned'), existing['last_cleaned'] or ''),
            sanitize_text(payload.get('notes'), existing['notes'] or ''),
            now,
            bin_id,
        ),
    )
    row = query_one(
        """
        SELECT bins.*, users.full_name AS assigned_user_name
        FROM bins LEFT JOIN users ON users.id = bins.assigned_user_id
        WHERE bins.id = ?
        """,
        (bin_id,),
    )
    return jsonify(row_to_bin(row))


@app.route('/api/bins/<int:bin_id>', methods=['DELETE'])
@roles_required('admin', 'city_head')
def api_bins_delete(bin_id):
    if query_one("SELECT id FROM bins WHERE id = ?", (bin_id,)) is None:
        return jsonify({'error': 'bin not found'}), 404
    execute("DELETE FROM bins WHERE id = ?", (bin_id,))
    return jsonify({'success': True})


@app.route('/api/tasks')
@login_required
def api_tasks_list():
    return jsonify(fetch_tasks_for_user(current_user()))


@app.route('/api/tasks', methods=['POST'])
@roles_required('admin', 'city_head')
def api_tasks_create():
    payload = json_body()
    title = sanitize_text(payload.get('title'))
    if not title:
        return jsonify({'error': 'title is required'}), 400

    priority = sanitize_text(payload.get('priority'), 'medium').lower()
    status = sanitize_text(payload.get('status'), 'pending').lower()
    if priority not in TASK_PRIORITY_OPTIONS or status not in TASK_STATUS_OPTIONS:
        return jsonify({'error': 'invalid task priority or status'}), 400

    now = utc_now()
    cursor = execute(
        """
        INSERT INTO tasks (
            title, description, zone, priority, status, due_at, assigned_user_id, bin_id,
            created_by_user_id, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            sanitize_text(payload.get('description')),
            sanitize_text(payload.get('zone')),
            priority,
            status,
            sanitize_text(payload.get('dueAt')),
            parse_int(payload.get('assignedUserId')),
            parse_int(payload.get('binId')),
            current_user()['id'],
            sanitize_text(payload.get('notes')),
            now,
            now,
        ),
    )
    row = query_one(
        """
        SELECT tasks.*, assigned.full_name AS assigned_user_name, bins.bin_code AS bin_code,
               creator.full_name AS created_by_name
        FROM tasks
        LEFT JOIN users AS assigned ON assigned.id = tasks.assigned_user_id
        LEFT JOIN bins ON bins.id = tasks.bin_id
        LEFT JOIN users AS creator ON creator.id = tasks.created_by_user_id
        WHERE tasks.id = ?
        """,
        (cursor.lastrowid,),
    )
    return jsonify(row_to_task(row)), 201


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
@login_required
def api_tasks_update(task_id):
    user = current_user()
    payload = json_body()
    existing = query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if existing is None:
        return jsonify({'error': 'task not found'}), 404

    now = utc_now()
    if user['role'] == 'staff':
        if existing['assigned_user_id'] != user['id']:
            return jsonify({'error': 'forbidden'}), 403
        status = sanitize_text(payload.get('status'), existing['status']).lower()
        if status not in TASK_STATUS_OPTIONS:
            return jsonify({'error': 'invalid task status'}), 400
        execute(
            "UPDATE tasks SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
            (status, sanitize_text(payload.get('notes'), existing['notes'] or ''), now, task_id),
        )
    else:
        priority = sanitize_text(payload.get('priority'), existing['priority']).lower()
        status = sanitize_text(payload.get('status'), existing['status']).lower()
        if priority not in TASK_PRIORITY_OPTIONS or status not in TASK_STATUS_OPTIONS:
            return jsonify({'error': 'invalid task priority or status'}), 400
        execute(
            """
            UPDATE tasks
            SET title = ?, description = ?, zone = ?, priority = ?, status = ?, due_at = ?,
                assigned_user_id = ?, bin_id = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                sanitize_text(payload.get('title'), existing['title']),
                sanitize_text(payload.get('description'), existing['description'] or ''),
                sanitize_text(payload.get('zone'), existing['zone'] or ''),
                priority,
                status,
                sanitize_text(payload.get('dueAt'), existing['due_at'] or ''),
                parse_int(payload.get('assignedUserId'), existing['assigned_user_id']),
                parse_int(payload.get('binId'), existing['bin_id']),
                sanitize_text(payload.get('notes'), existing['notes'] or ''),
                now,
                task_id,
            ),
        )

    row = query_one(
        """
        SELECT tasks.*, assigned.full_name AS assigned_user_name, bins.bin_code AS bin_code,
               creator.full_name AS created_by_name
        FROM tasks
        LEFT JOIN users AS assigned ON assigned.id = tasks.assigned_user_id
        LEFT JOIN bins ON bins.id = tasks.bin_id
        LEFT JOIN users AS creator ON creator.id = tasks.created_by_user_id
        WHERE tasks.id = ?
        """,
        (task_id,),
    )
    return jsonify(row_to_task(row))


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
@roles_required('admin', 'city_head')
def api_tasks_delete(task_id):
    if query_one("SELECT id FROM tasks WHERE id = ?", (task_id,)) is None:
        return jsonify({'error': 'task not found'}), 404
    execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return jsonify({'success': True})


@app.route('/api/alerts')
@login_required
def api_alerts_list():
    return jsonify(fetch_alerts_for_user(current_user()))


@app.route('/api/alerts', methods=['POST'])
@roles_required('admin', 'city_head')
def api_alerts_create():
    payload = json_body()
    title = sanitize_text(payload.get('title'))
    message = sanitize_text(payload.get('message'))
    priority = sanitize_text(payload.get('priority'), 'medium').lower()
    status = sanitize_text(payload.get('status'), 'open').lower()

    if not title or not message:
        return jsonify({'error': 'title and message are required'}), 400
    if priority not in ALERT_PRIORITY_OPTIONS or status not in ALERT_STATUS_OPTIONS:
        return jsonify({'error': 'invalid alert priority or status'}), 400

    now = utc_now()
    cursor = execute(
        """
        INSERT INTO alerts (
            title, message, priority, status, user_id, bin_id, created_by_user_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            message,
            priority,
            status,
            parse_int(payload.get('userId')),
            parse_int(payload.get('binId')),
            current_user()['id'],
            now,
            now,
        ),
    )
    row = query_one(
        """
        SELECT alerts.*, users.full_name AS user_name, bins.bin_code AS bin_code,
               creator.full_name AS created_by_name
        FROM alerts
        LEFT JOIN users ON users.id = alerts.user_id
        LEFT JOIN bins ON bins.id = alerts.bin_id
        LEFT JOIN users AS creator ON creator.id = alerts.created_by_user_id
        WHERE alerts.id = ?
        """,
        (cursor.lastrowid,),
    )
    return jsonify(row_to_alert(row)), 201


@app.route('/api/alerts/<int:alert_id>', methods=['PUT'])
@login_required
def api_alerts_update(alert_id):
    user = current_user()
    payload = json_body()
    existing = query_one("SELECT * FROM alerts WHERE id = ?", (alert_id,))
    if existing is None:
        return jsonify({'error': 'alert not found'}), 404

    now = utc_now()
    if user['role'] == 'staff':
        status = sanitize_text(payload.get('status'), existing['status']).lower()
        if status not in ALERT_STATUS_OPTIONS:
            return jsonify({'error': 'invalid alert status'}), 400
        execute("UPDATE alerts SET status = ?, updated_at = ? WHERE id = ?", (status, now, alert_id))
    else:
        priority = sanitize_text(payload.get('priority'), existing['priority']).lower()
        status = sanitize_text(payload.get('status'), existing['status']).lower()
        if priority not in ALERT_PRIORITY_OPTIONS or status not in ALERT_STATUS_OPTIONS:
            return jsonify({'error': 'invalid alert priority or status'}), 400
        execute(
            """
            UPDATE alerts
            SET title = ?, message = ?, priority = ?, status = ?, user_id = ?, bin_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                sanitize_text(payload.get('title'), existing['title']),
                sanitize_text(payload.get('message'), existing['message']),
                priority,
                status,
                parse_int(payload.get('userId'), existing['user_id']),
                parse_int(payload.get('binId'), existing['bin_id']),
                now,
                alert_id,
            ),
        )

    row = query_one(
        """
        SELECT alerts.*, users.full_name AS user_name, bins.bin_code AS bin_code,
               creator.full_name AS created_by_name
        FROM alerts
        LEFT JOIN users ON users.id = alerts.user_id
        LEFT JOIN bins ON bins.id = alerts.bin_id
        LEFT JOIN users AS creator ON creator.id = alerts.created_by_user_id
        WHERE alerts.id = ?
        """,
        (alert_id,),
    )
    return jsonify(row_to_alert(row))


@app.route('/api/alerts/<int:alert_id>', methods=['DELETE'])
@roles_required('admin', 'city_head')
def api_alerts_delete(alert_id):
    if query_one("SELECT id FROM alerts WHERE id = ?", (alert_id,)) is None:
        return jsonify({'error': 'alert not found'}), 404
    execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    return jsonify({'success': True})


@app.route('/api/reports')
@roles_required('admin', 'city_head')
def api_reports_list():
    return jsonify(generated_reports_payload(current_user()))


@app.route('/api/validations')
@login_required
def api_validations_list():
    return jsonify(fetch_validations_for_user(current_user()))


@app.route('/api/validations/<int:validation_id>', methods=['PUT'])
@roles_required('admin', 'city_head')
def api_validations_update(validation_id):
    payload = json_body()
    existing = query_one("SELECT * FROM validation_runs WHERE id = ?", (validation_id,))
    if existing is None:
        return jsonify({'error': 'validation record not found'}), 404

    review_status = sanitize_text(payload.get('reviewStatus'), existing['review_status']).lower()
    if review_status not in VALIDATION_REVIEW_STATUS_OPTIONS:
        return jsonify({'error': 'invalid review status'}), 400

    now = utc_now()
    execute(
        """
        UPDATE validation_runs
        SET review_status = ?, review_notes = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            review_status,
            sanitize_text(payload.get('reviewNotes'), existing['review_notes'] or ''),
            now,
            validation_id,
        ),
    )
    row = query_one(
        """
        SELECT validation_runs.*, bins.bin_code AS bin_code, users.full_name AS created_by_name
        FROM validation_runs
        LEFT JOIN bins ON bins.id = validation_runs.bin_id
        LEFT JOIN users ON users.id = validation_runs.created_by_user_id
        WHERE validation_runs.id = ?
        """,
        (validation_id,),
    )
    return jsonify(row_to_validation(row))


@app.route('/api/validations/<int:validation_id>', methods=['DELETE'])
@roles_required('admin', 'city_head')
def api_validations_delete(validation_id):
    existing = query_one("SELECT * FROM validation_runs WHERE id = ?", (validation_id,))
    if existing is None:
        return jsonify({'error': 'validation record not found'}), 404

    if existing['image_name']:
        image_path = os.path.join(UPLOAD_DIR, existing['image_name'])
        if os.path.exists(image_path):
            os.remove(image_path)
    execute("DELETE FROM validation_runs WHERE id = ?", (validation_id,))
    return jsonify({'success': True})


@app.route('/api/sensor/latest')
def api_sensor_latest():
    return jsonify(get_sensor_snapshot())


@app.route('/data')
def legacy_sensor_data():
    return jsonify(get_legacy_sensor_snapshot())


@app.route('/api/reading', methods=['POST'])
def api_reading():
    if SENSOR_API_KEY and request.headers.get('X-API-KEY') != SENSOR_API_KEY:
        return jsonify({'error': 'invalid api key'}), 401

    payload = request.get_json(silent=True) or request.form.to_dict()
    distance_cm = parse_distance_value(payload.get('distance_cm'))
    distance_inch = parse_distance_value(payload.get('distance_inch'))
    if distance_cm is None and distance_inch is None:
        return jsonify({'error': 'distance_cm or distance_inch is required'}), 400

    snapshot = update_sensor_snapshot(
        distance_cm=distance_cm,
        distance_inch=distance_inch,
        raw=json.dumps(payload, ensure_ascii=True),
        source='http',
        device_id=sanitize_text(payload.get('device_id'), DEFAULT_DEVICE_ID),
        status='HTTP sensor update received',
    )
    return jsonify(snapshot)


@app.route('/api/validate', methods=['POST'])
@login_required
def api_validate():
    if 'image' not in request.files:
        return jsonify({'error': 'image file is required'}), 400

    image_file = request.files['image']
    if image_file.filename == '':
        return jsonify({'error': 'please choose an image'}), 400
    if not allowed_image(image_file.filename):
        return jsonify({'error': 'unsupported image format'}), 400

    bin_id = parse_int(request.form.get('bin_id'))
    bin_row = query_one("SELECT * FROM bins WHERE id = ?", (bin_id,)) if bin_id else None
    location = sanitize_text(request.form.get('location'), bin_row['location'] if bin_row else '')

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(image_file.filename)}"
    image_path = os.path.join(UPLOAD_DIR, filename)
    image_file.save(image_path)

    try:
        prediction = predict_image_class(image_path)
    except FileNotFoundError as exc:
        if os.path.exists(image_path):
            os.remove(image_path)
        return jsonify({'error': str(exc)}), 400
    except UnidentifiedImageError:
        if os.path.exists(image_path):
            os.remove(image_path)
        return jsonify({'error': 'the uploaded file is not a valid image. Please choose a clear JPG or PNG bin photo.'}), 400
    except Exception:
        if os.path.exists(image_path):
            os.remove(image_path)
        app.logger.exception('Failed to process uploaded validation image')
        return jsonify({'error': 'unable to process the uploaded image. Please try another clear bin photo.'}), 500

    sensor_values = resolve_sensor_values(request.form)
    match = compare_levels(prediction['ai_level'], sensor_values['level'])
    now = utc_now()

    cursor = execute(
        """
        INSERT INTO validation_runs (
            bin_id, created_by_user_id, location_snapshot, image_name, image_path, sensor_distance_cm,
            sensor_fill_percent, sensor_level, sensor_source, sensor_status, ai_level, confidence,
            probabilities_json, match_result, review_status, review_notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', '', ?, ?)
        """,
        (
            bin_id,
            current_user()['id'],
            location,
            filename,
            image_path,
            sensor_values['distance_cm'],
            sensor_values['fill_percent'],
            sensor_values['level'],
            sensor_values['source'],
            sensor_values['status'],
            prediction['ai_level'],
            prediction['confidence'],
            json.dumps(prediction['probabilities']),
            match,
            now,
            now,
        ),
    )

    update_bin_from_validation(bin_id, sensor_values)

    row = query_one(
        """
        SELECT validation_runs.*, bins.bin_code AS bin_code, users.full_name AS created_by_name
        FROM validation_runs
        LEFT JOIN bins ON bins.id = validation_runs.bin_id
        LEFT JOIN users ON users.id = validation_runs.created_by_user_id
        WHERE validation_runs.id = ?
        """,
        (cursor.lastrowid,),
    )
    return jsonify(row_to_validation(row)), 201


@app.route('/uploads/<path:filename>')
def uploads(filename):
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == '__main__':
    start_sensor_worker()
    app.run(host='0.0.0.0', port=5000, debug=False)
