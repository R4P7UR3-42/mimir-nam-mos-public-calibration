"""Frozen GFS MOS profile applied to the shared semantic capture/evaluator."""


PREDECLARATION_SHA256 = "a8e918940041513a14219b88ac3e92a17577a0b14d22538f37d302f0eb6586d0"


def configure(capture_module) -> None:
    capture_module.SCHEMA = "gfs_mos_station_rolling_capture_v1"
    capture_module.MODEL_IDENTITY = "gfs_mos_station_rolling_wilson90_v1"
    capture_module.PREDECLARATION_SHA256 = PREDECLARATION_SHA256
    capture_module.SOURCE_MODEL = "GFS"
    capture_module.FORECAST_MODEL = "noaa_gfs_station_mos_n_x"
    capture_module.DUPLICATE_COMPARE_FIELDS = set(capture_module.REQUIRED_MOS_FIELDS)
    capture_module.EXPECTED_EXACT_DUPLICATES_PER_STATION = None
    capture_module.REQUIRE_GLOBAL_OPTIONAL_SCHEMA = False
