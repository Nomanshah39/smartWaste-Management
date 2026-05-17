from config import BIN_HEIGHT_CM, LOW_FILL_THRESHOLD_PERCENT, MEDIUM_FILL_THRESHOLD_PERCENT


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


def resolve_fill_thresholds(
    low_threshold_percent: float | None = None,
    medium_threshold_percent: float | None = None,
) -> tuple[float, float]:
    low_percent = LOW_FILL_THRESHOLD_PERCENT if low_threshold_percent is None else float(low_threshold_percent)
    medium_percent = MEDIUM_FILL_THRESHOLD_PERCENT if medium_threshold_percent is None else float(medium_threshold_percent)
    low_percent = max(0.0, min(100.0, round(low_percent, 2)))
    medium_percent = max(low_percent, min(100.0, round(medium_percent, 2)))
    return low_percent, medium_percent


def sensor_distance_to_level(
    distance_cm: float,
    bin_height_cm: float | None = None,
    low_threshold_percent: float | None = None,
    medium_threshold_percent: float | None = None,
) -> str:
    if distance_cm is None:
        return 'unknown'
    fill_percent = sensor_distance_to_fill_percent(distance_cm, bin_height_cm)
    if fill_percent is None:
        return 'unknown'
    low_percent, medium_percent = resolve_fill_thresholds(low_threshold_percent, medium_threshold_percent)
    if fill_percent < low_percent:
        return 'low'
    if fill_percent < medium_percent:
        return 'medium'
    return 'high'


def sensor_distance_to_fill_percent(distance_cm: float, bin_height_cm: float | None = None) -> float | None:
    if distance_cm is None:
        return None
    height_cm = BIN_HEIGHT_CM if bin_height_cm is None else float(bin_height_cm)
    if height_cm <= 0:
        return None
    fill_percent = 100.0 * (1.0 - (distance_cm / height_cm))
    return max(0.0, min(100.0, round(fill_percent, 2)))


def compare_levels(ai_level: str, sensor_level: str) -> str:
    ai_level = normalize_level_name(ai_level)
    sensor_level = normalize_level_name(sensor_level)
    if ai_level == 'unknown' or sensor_level == 'unknown':
        return 'Unavailable'
    return 'Match' if ai_level == sensor_level else 'Mismatch'
