import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_ZIP_PATH = os.path.join(BASE_DIR, 'FINAL_3_LEVEL_DATASET.zip')
DATASET_DIR = os.path.join(BASE_DIR, 'FINAL_3_LEVEL_DATASET')
DATABASE_PATH = os.path.join(BASE_DIR, 'smartwaste.db')
MODEL_DIR = os.path.join(BASE_DIR, 'saved_models')
MODEL_PATH = os.path.join(MODEL_DIR, 'waste_level_model.keras')
TRAINING_SUMMARY_PATH = os.path.join(MODEL_DIR, 'training_summary.json')
TRAINING_PLOT_PATH = os.path.join(MODEL_DIR, 'training_curves.png')
VALIDATION_HISTORY_PATH = os.path.join(MODEL_DIR, 'validation_history.json')
LABELS_CSV_PATH = os.path.join(DATASET_DIR, 'labels.csv')
CLASS_NAMES = ['high', 'low', 'medium']
IMG_SIZE = (224, 224)
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '10'))
SECRET_KEY = os.getenv('SECRET_KEY', 'smartwaste-dev-secret-key')
DEFAULT_ADMIN_USERNAME = os.getenv('DEFAULT_ADMIN_USERNAME', 'admin')
DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')
SENSOR_MODE = os.getenv('SENSOR_MODE', 'auto').strip().lower()
SERIAL_PORT = os.getenv('SERIAL_PORT', 'COM6')
BAUD_RATE = int(os.getenv('BAUD_RATE', '115200'))
SENSOR_API_KEY = os.getenv('SENSOR_API_KEY', 'my_ultrasonic_token')
DEFAULT_DEVICE_ID = os.getenv('DEFAULT_DEVICE_ID', 'esp8266-ultrasonic')
BIN_DEPTH_CM = float(os.getenv('BIN_DEPTH_CM', '30'))
LOW_THRESHOLD_CM = float(os.getenv('LOW_THRESHOLD_CM', '20'))
MEDIUM_THRESHOLD_CM = float(os.getenv('MEDIUM_THRESHOLD_CM', '10'))
# distance > LOW_THRESHOLD_CM => low
# MEDIUM_THRESHOLD_CM < distance <= LOW_THRESHOLD_CM => medium
# distance <= MEDIUM_THRESHOLD_CM => high
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
