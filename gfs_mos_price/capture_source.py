#!/usr/bin/env python3
"""Capture frozen price-OOS GFS MOS and NOAA outcome sources."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import capture  # noqa: E402
from gfs_mos_price.profile import configure  # noqa: E402


configure(capture)

if __name__ == "__main__":
    capture.main()
