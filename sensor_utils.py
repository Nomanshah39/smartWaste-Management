from config import LOW_THRESHOLD_CM, MEDIUM_THRESHOLD_CM
from config import BIN_DEPTH_CM


def normalize_level_name(level) -> str:
    if level is None:
        return 'unknown'
    level = str(level).strip().lower()
    aliases = {
        'low': 'low',
        'medium': 'medium',
        'med': 'medium',
        'mid': 'medium',
        'high': 'high',
    }
    return aliases.get(level, 'unknown')


def sensor_distance_to_level(distance_cm: float) -> str:
    if distance_cm is None:
        return 'unknown'
    if distance_cm > LOW_THRESHOLD_CM:
        return 'low'
    if distance_cm > MEDIUM_THRESHOLD_CM:
        return 'medium'
    return 'high'


def sensor_distance_to_fill_percent(distance_cm: float) -> float | None:
    if distance_cm is None:
        return None
    if BIN_DEPTH_CM <= 0:
        return None
    fill_percent = 100.0 * (1.0 - (distance_cm / BIN_DEPTH_CM))
    return max(0.0, min(100.0, round(fill_percent, 2)))


def compare_levels(ai_level: str, sensor_level: str) -> str:
    ai_level = normalize_level_name(ai_level)
    sensor_level = normalize_level_name(sensor_level)
    if ai_level == 'unknown' or sensor_level == 'unknown':
        return 'Unavailable'
    return 'Match' if ai_level == sensor_level else 'Mismatch'
