"""Frozen GFS MOS economic-OOS source profile."""

import datetime as dt


PREDECLARATION_SHA256 = "57e0b81fcf181e081dd554bfa04143aae6d26b7a54bbf849039e1114c8af54ea"
STATIONS_SHA256 = "4b1d30b1feda203d0b7b482778104a98be475ed6ec73bc64e3da9bf130154558"


def configure(capture_module) -> None:
    capture_module.SCHEMA = "gfs_mos_executable_oos_source_capture_v1"
    capture_module.MODEL_IDENTITY = "gfs_mos_station_rolling_wilson90_executable_no_oos_v1"
    capture_module.PREDECLARATION_SHA256 = PREDECLARATION_SHA256
    capture_module.STATIONS_SHA256 = STATIONS_SHA256
    capture_module.CALIBRATION_START = dt.date(2025, 9, 1)
    capture_module.CALIBRATION_END = dt.date(2025, 12, 30)
    capture_module.EVALUATION_START = dt.date(2025, 12, 31)
    capture_module.EVALUATION_END = dt.date(2026, 6, 28)
    capture_module.SOURCE_MODEL = "GFS"
    capture_module.FORECAST_MODEL = "noaa_gfs_station_mos_n_x"
    capture_module.DUPLICATE_COMPARE_FIELDS = set(capture_module.REQUIRED_MOS_FIELDS)
    capture_module.EXPECTED_EXACT_DUPLICATES_PER_STATION = None
    capture_module.REQUIRE_GLOBAL_OPTIONAL_SCHEMA = False
    capture_module.EXPECTED_CALIBRATION_DATES = 121
    capture_module.EXPECTED_EVALUATION_DATES = 180
    capture_module.EXPECTED_STATION_COUNT = 10
    capture_module.EXPECTED_NETWORK_REQUESTS = 13
    capture_module.SOURCE_FILE_PREFIX = "iem-gfs-mos"
