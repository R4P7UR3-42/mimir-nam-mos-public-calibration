#!/usr/bin/env python3
"""Evaluate the single frozen NOAA GEFSv12 dispersion hypothesis."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


CAPTURE_SCHEMA = "noaa_gefs_v12_dispersion_capture_v1"
ROW_SCHEMA = "noaa_gefs_v12_dispersion_member_row_v1"
EVALUATION_SCHEMA = "noaa_gefs_v12_dispersion_evaluation_v1"
MODEL_IDENTITY = "noaa_gefs_v12_five_member_station_z_wilson95_rolling120_lag2_v1"
PREDECLARATION_SHA256 = "7bc055938dcb0332e94dd6486f5249be2fa6eef632cf2d5ee44524274036f9d0"
MEMBERS = ("c00", "p01", "p02", "p03", "p04")
EVALUATION_START = dt.date(2019, 4, 26)
EVALUATION_END = dt.date(2019, 12, 31)
BOOTSTRAP_SAMPLES = 20_000
WILSON_Z95 = 1.6448536269514722


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def date_range(start: dt.date, end: dt.date) -> list[dt.date]:
    values: list[dt.date] = []
    current = start
    while current <= end:
        values.append(current)
        current += dt.timedelta(days=1)
    return values


def wilson_lower(successes: int, total: int, z: float = WILSON_Z95) -> float:
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("Wilson inputs are invalid.")
    proportion = successes / total
    denominator = 1 + z * z / total
    center = proportion + z * z / (2 * total)
    radius = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
    return (center - radius) / denominator


def clustered_lower(rows: list[dict[str, object]], value_key: str, tail: float, seed: int) -> float | None:
    clusters: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        clusters[str(row["market_date"])].append(float(row[value_key]))
    ordered = [clusters[key] for key in sorted(clusters)]
    if not ordered:
        return None
    summaries = [(sum(cluster), len(cluster)) for cluster in ordered]
    state = seed & 0xFFFFFFFF
    means: list[float] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        total = 0.0
        count = 0
        for _ in range(len(summaries)):
            state = (state * 1_664_525 + 1_013_904_223) & 0xFFFFFFFF
            cluster_sum, cluster_count = summaries[(state * len(summaries)) // 0x1_0000_0000]
            total += cluster_sum
            count += cluster_count
        means.append(total / count)
    means.sort()
    return means[math.floor((BOOTSTRAP_SAMPLES - 1) * tail)]


def score_band(score: float) -> str:
    if 0.90 <= score < 0.93:
        return "0.90_0.93"
    if 0.93 <= score < 0.96:
        return "0.93_0.96"
    if 0.96 <= score <= 1.0:
        return "0.96_1.00"
    raise ValueError(f"Emitted score is outside frozen bands: {score}.")


def load_capture(root: Path) -> tuple[dict[str, object], dict[tuple[str, str], dict[str, object]], dict[tuple[str, str], float]]:
    capture_path = root / "capture.json"
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    if (
        capture.get("schema") != CAPTURE_SCHEMA
        or capture.get("model_identity") != MODEL_IDENTITY
        or capture.get("predeclaration_sha256") != PREDECLARATION_SHA256
        or capture.get("research_only") is not True
        or capture.get("active_trading_capability_changed") is not False
        or capture.get("production_database_accessed") is not False
        or capture.get("coverage") != {
            "target_dates": 370,
            "evaluation_dates": 250,
            "stations": 20,
            "member_rows": 1850,
            "outcomes": 7400,
        }
    ):
        raise ValueError("GEFS capture identity/coverage is invalid.")
    rows: dict[tuple[str, str], dict[str, object]] = {}
    manifest = capture.get("row_manifest")
    if not isinstance(manifest, list) or len(manifest) != 1850:
        raise ValueError("GEFS row manifest is incomplete.")
    for item in manifest:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            raise ValueError("GEFS row manifest entry is malformed.")
        path = root / item["path"]
        if not path.is_relative_to(root) or sha256(path.read_bytes()) != item["sha256"]:
            raise ValueError("GEFS row checksum is invalid.")
        row = json.loads(path.read_text(encoding="utf-8"))
        key = (str(row.get("target_market_date")), str(row.get("member")))
        if (
            row.get("schema") != ROW_SCHEMA
            or row.get("model_identity") != MODEL_IDENTITY
            or key in rows
            or key[1] not in MEMBERS
            or not isinstance(row.get("station_highs"), list)
            or len(row["station_highs"]) != 20
        ):
            raise ValueError("GEFS member row identity is invalid.")
        rows[key] = row
    outcomes_path = root / "outcomes.json"
    if sha256(outcomes_path.read_bytes()) != capture.get("outcomes_sha256"):
        raise ValueError("GEFS outcome checksum is invalid.")
    outcome_payload = json.loads(outcomes_path.read_text(encoding="utf-8"))
    if outcome_payload.get("schema") != "noaa_gefs_v12_dispersion_outcomes_v1" or not isinstance(outcome_payload.get("rows"), list):
        raise ValueError("GEFS outcome identity is invalid.")
    outcomes: dict[tuple[str, str], float] = {}
    for row in outcome_payload["rows"]:
        key = (str(row.get("station_id")), str(row.get("market_date")))
        if key in outcomes:
            raise ValueError("GEFS outcomes contain a duplicate.")
        outcomes[key] = float(row["high_temp_f"])
    if len(outcomes) != 7400:
        raise ValueError("GEFS outcomes are incomplete.")
    return capture, rows, outcomes


def build_features(
    member_rows: dict[tuple[str, str], dict[str, object]], outcomes: dict[tuple[str, str], float]
) -> dict[tuple[str, str], dict[str, float]]:
    by_target_station: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    grid_identity: dict[str, tuple[float, float]] = {}
    for (market_date, member), row in member_rows.items():
        for station_row in row["station_highs"]:
            station = str(station_row["station_id"])
            key = (market_date, station)
            if member in by_target_station[key]:
                raise ValueError("GEFS member high is duplicated.")
            kelvin = float(station_row["member_high_kelvin"])
            if not math.isfinite(kelvin):
                raise ValueError("GEFS member high is non-finite.")
            by_target_station[key][member] = (kelvin - 273.15) * 9 / 5 + 32
            grid = (float(station_row["grid_latitude"]), float(station_row["grid_longitude"]))
            if station in grid_identity and grid_identity[station] != grid:
                raise ValueError(f"GEFS grid identity drifted for {station}.")
            grid_identity[station] = grid
    features: dict[tuple[str, str], dict[str, float]] = {}
    for key, values in by_target_station.items():
        outcome_key = (key[1], key[0])
        if tuple(sorted(values)) != tuple(sorted(MEMBERS)) or outcome_key not in outcomes:
            raise ValueError(f"GEFS feature coverage is incomplete for {key}.")
        ordered = [values[member] for member in MEMBERS]
        center = statistics.fmean(ordered)
        raw_dispersion = statistics.stdev(ordered)
        dispersion = max(raw_dispersion, 0.5)
        features[(key[1], key[0])] = {
            "center_f": center,
            "raw_dispersion_f": raw_dispersion,
            "dispersion_f": dispersion,
            "outcome_f": outcomes[outcome_key],
            "standardized_error": (outcomes[outcome_key] - center) / dispersion,
        }
    if len(features) != 7400:
        raise ValueError("GEFS derived feature coverage is incomplete.")
    return features


def build_predictions(features: dict[tuple[str, str], dict[str, float]]) -> list[dict[str, object]]:
    evaluation_dates = date_range(EVALUATION_START, EVALUATION_END)
    stations = sorted({station for station, _ in features})
    if len(stations) != 20 or len(evaluation_dates) != 250:
        raise ValueError("GEFS evaluation inventory is invalid.")
    predictions: list[dict[str, object]] = []
    for market_date in evaluation_dates:
        market_text = market_date.isoformat()
        calibration_dates = date_range(market_date - dt.timedelta(days=120), market_date - dt.timedelta(days=2))
        if len(calibration_dates) != 119:
            raise ValueError("GEFS rolling calibration clock is invalid.")
        for station in stations:
            current = features[(station, market_text)]
            prior = [features[(station, date.isoformat())]["standardized_error"] for date in calibration_dates]
            if len(prior) != 119:
                raise ValueError("GEFS station calibration sample is incomplete.")
            for distance in (4, 5, 6, 7):
                threshold = math.ceil(current["center_f"] + distance)
                threshold_z = (threshold - current["center_f"]) / current["dispersion_f"]
                successes = sum(value <= threshold_z for value in prior)
                score = wilson_lower(successes, len(prior))
                if score < 0.90:
                    continue
                outcome = 1 if current["outcome_f"] <= threshold else 0
                predictions.append({
                    "station_id": station,
                    "market_date": market_text,
                    "distance_index": distance,
                    "threshold_f": threshold,
                    "threshold_distance_f": threshold - current["center_f"],
                    "ensemble_center_f": current["center_f"],
                    "ensemble_raw_dispersion_f": current["raw_dispersion_f"],
                    "ensemble_dispersion_f": current["dispersion_f"],
                    "calibration_dates": len(prior),
                    "calibration_successes": successes,
                    "score": score,
                    "outcome_no": outcome,
                    "margin": outcome - score,
                    "brier": (score - outcome) ** 2,
                })
    return predictions


def summarize_rows(rows: list[dict[str, object]], seed: int) -> dict[str, object]:
    if not rows:
        return {
            "predictions": 0,
            "independent_market_dates": 0,
            "stations": 0,
            "successes": 0,
            "mean_score": None,
            "observed_success_rate": None,
            "observed_minus_score": None,
            "clustered_90_lower_margin": None,
            "clustered_95_lower_margin": None,
        }
    count = len(rows)
    successes = sum(int(row["outcome_no"]) for row in rows)
    mean_score = sum(float(row["score"]) for row in rows) / count
    observed = successes / count
    return {
        "predictions": count,
        "independent_market_dates": len({str(row["market_date"]) for row in rows}),
        "stations": len({str(row["station_id"]) for row in rows}),
        "successes": successes,
        "mean_score": mean_score,
        "observed_success_rate": observed,
        "observed_minus_score": observed - mean_score,
        "clustered_90_lower_margin": clustered_lower(rows, "margin", 0.10, seed),
        "clustered_95_lower_margin": clustered_lower(rows, "margin", 0.05, seed),
    }


def evaluate(predictions: list[dict[str, object]]) -> dict[str, object]:
    summary = summarize_rows(predictions, 0x6E6F6161)
    count = len(predictions)
    observed = float(summary["observed_success_rate"]) if count else 0.0
    brier = sum(float(row["brier"]) for row in predictions) / count if count else None
    climatology_brier = observed * (1 - observed) if count else None
    brier_skill = 1 - brier / climatology_brier if brier is not None and climatology_brier else None

    bands = []
    for index, band in enumerate(("0.90_0.93", "0.93_0.96", "0.96_1.00"), start=1):
        rows = [row for row in predictions if score_band(float(row["score"])) == band]
        band_summary = summarize_rows(rows, 0x6E6F6161 + index)
        error = abs(float(band_summary["observed_minus_score"])) if rows else None
        bands.append({
            "band": band,
            **band_summary,
            "absolute_reliability_error": error,
            "passes": bool(
                rows
                and int(band_summary["independent_market_dates"]) >= 30
                and error is not None
                and error <= 0.05
                and float(band_summary["clustered_90_lower_margin"]) >= 0
            ),
        })
    populated_bands = [band for band in bands if int(band["predictions"]) > 0]

    station_counts = Counter(str(row["station_id"]) for row in predictions)
    date_counts = Counter(str(row["market_date"]) for row in predictions)
    maximum_station_share = max(station_counts.values(), default=0) / count if count else None
    maximum_date_share = max(date_counts.values(), default=0) / count if count else None
    holdouts = []
    for index, station in enumerate(sorted(station_counts), start=1):
        rows = [row for row in predictions if row["station_id"] != station]
        holdout = summarize_rows(rows, 0x6E6F6200 + index)
        holdouts.append({
            "excluded_station": station,
            **holdout,
            "passes": bool(
                rows
                and float(holdout["observed_minus_score"]) >= 0
                and float(holdout["clustered_95_lower_margin"]) >= 0
            ),
        })

    gates = {
        "exactly_250_independent_market_dates": summary["independent_market_dates"] == 250,
        "at_least_10_stations": summary["stations"] >= 10,
        "at_least_500_predictions": summary["predictions"] >= 500,
        "at_least_two_populated_bands": len(populated_bands) >= 2,
        "every_populated_band_has_30_dates": bool(populated_bands) and all(band["independent_market_dates"] >= 30 for band in populated_bands),
        "positive_brier_skill": brier_skill is not None and brier_skill > 0,
        "nonnegative_clustered_90_margin": summary["clustered_90_lower_margin"] is not None and summary["clustered_90_lower_margin"] >= 0,
        "nonnegative_clustered_95_margin": summary["clustered_95_lower_margin"] is not None and summary["clustered_95_lower_margin"] >= 0,
        "every_populated_band_reliable": bool(populated_bands) and all(band["passes"] for band in populated_bands),
        "maximum_station_share_at_most_0_20": maximum_station_share is not None and maximum_station_share <= 0.20,
        "maximum_date_share_at_most_0_02": maximum_date_share is not None and maximum_date_share <= 0.02,
        "every_leave_one_station_out_passes": len(holdouts) >= 10 and all(row["passes"] for row in holdouts),
    }
    return {
        **summary,
        "brier_score": brier,
        "evaluation_climatology_brier_score": climatology_brier,
        "brier_skill_versus_evaluation_climatology": brier_skill,
        "maximum_station_share": maximum_station_share,
        "maximum_date_share": maximum_date_share,
        "reliability_bands": bands,
        "leave_one_station_out_calibration": holdouts,
        "diagnostic_gates": gates,
        "calibration_diagnostic_pass": all(gates.values()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    capture_dir = Path(args.capture_dir).resolve()
    capture, member_rows, outcomes = load_capture(capture_dir)
    features = build_features(member_rows, outcomes)
    predictions = build_predictions(features)
    result = evaluate(predictions)
    report = {
        "schema": EVALUATION_SCHEMA,
        "model_identity": MODEL_IDENTITY,
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "capture_sha256": sha256((capture_dir / "capture.json").read_bytes()),
        "design": capture["design"],
        "evaluation": result,
        "predictions": predictions,
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "independent_oos_calibration_evidence": bool(result["calibration_diagnostic_pass"]),
        "executable_economics_evidence": False,
        "capital_risk_authority": False,
        "production_activation": False,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": report["schema"],
        "model_identity": MODEL_IDENTITY,
        "evaluation": {key: value for key, value in result.items() if key not in {"reliability_bands", "leave_one_station_out_calibration"}},
        "reliability_bands": result["reliability_bands"],
        "leave_one_station_out_calibration": result["leave_one_station_out_calibration"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
