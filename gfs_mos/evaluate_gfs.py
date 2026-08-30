#!/usr/bin/env python3
"""Evaluate the frozen GFS MOS rolling Wilson-90 hypothesis."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import capture  # noqa: E402
from gfs_mos.profile import configure  # noqa: E402


configure(capture)
import evaluate  # noqa: E402


evaluate.SCHEMA = "gfs_mos_station_rolling_evaluation_v1"
evaluate.MODEL_IDENTITY = capture.MODEL_IDENTITY

if __name__ == "__main__":
    evaluate.main()
