#!/usr/bin/env python3
"""Evaluate the single frozen NAM MOS v4 rolling Wilson-90 hypothesis."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path

import capture


getcontext().prec = 40
SCHEMA = "nam_mos_v4_station_rolling_evaluation_v1"
MODEL_IDENTITY = capture.MODEL_IDENTITY
Z90 = Decimal("1.2815515655446004")
SCORE_QUANTUM = Decimal("0.0001")
BOOTSTRAP_SAMPLES = 10_000
BANDS = (
    (Decimal("0.90"), Decimal("0.93"), "0.90-0.93"),
    (Decimal("0.93"), Decimal("0.96"), "0.93-0.96"),
    (Decimal("0.96"), Decimal("1.0001"), "0.96-1.00"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def validate_duplicate_counts(
    coverage: object,
    forecast_sources: object,
) -> None:
    expected_duplicate_rows = (
        20 * capture.EXPECTED_EXACT_DUPLICATES_PER_STATION
        if capture.EXPECTED_EXACT_DUPLICATES_PER_STATION is not None
        else None
    )
    if (
        not isinstance(coverage, dict)
        or not isinstance(coverage.get("selected_exact_duplicate_rows"), int)
        or coverage["selected_exact_duplicate_rows"] < 0
        or (
            expected_duplicate_rows is not None
            and coverage["selected_exact_duplicate_rows"] != expected_duplicate_rows
        )
        or not isinstance(forecast_sources, list)
        or len(forecast_sources) != 20
        or any(not isinstance(source, dict) for source in forecast_sources)
        or any(
            not isinstance(source.get("selected_exact_duplicate_count"), int)
            or source["selected_exact_duplicate_count"] < 0
            or (
                capture.EXPECTED_EXACT_DUPLICATES_PER_STATION is not None
                and source["selected_exact_duplicate_count"] != capture.EXPECTED_EXACT_DUPLICATES_PER_STATION
            )
            for source in forecast_sources
        )
        or sum(int(source["selected_exact_duplicate_count"]) for source in forecast_sources)
        != coverage["selected_exact_duplicate_rows"]
    ):
        raise ValueError("Capture duplicate count identity is invalid.")


def validate_capture_row(row: dict[str, object]) -> None:
    station = str(row.get("station_id", ""))
    try:
        market_date = dt.date.fromisoformat(str(row["market_date"]))
        forecast = Decimal(str(row["forecast_high_f"]))
        observed = Decimal(str(row["observed_high_f"]))
        residual = Decimal(str(row["residual_f"]))
    except (KeyError, ValueError) as error:
        raise ValueError(f"Capture row is malformed for {station}.") from error
    if not station or not all(value.is_finite() for value in (forecast, observed, residual)):
        raise ValueError(f"Capture row is non-finite for {station}|{market_date}.")
    if not Decimal("-100") <= forecast <= Decimal("150") or not Decimal("-100") <= observed <= Decimal("150"):
        raise ValueError(f"Capture temperature is outside bounds for {station}|{market_date}.")
    if residual != observed - forecast:
        raise ValueError(f"Capture residual identity conflicts for {station}|{market_date}.")
    initialized = market_date - dt.timedelta(days=1)
    expected = {
        "forecast_model": capture.FORECAST_MODEL,
        "forecast_initialized_at": f"{initialized.isoformat()}T12:00:00Z",
        "forecast_available_by": f"{initialized.isoformat()}T20:00:00Z",
        "forecast_time": f"{(market_date + dt.timedelta(days=1)).isoformat()}T00:00:00Z",
        "observation_source": "noaa_ncei_daily_summaries_tmax",
    }
    if any(row.get(key) != value for key, value in expected.items()):
        raise ValueError(f"Capture causal identity conflicts for {station}|{market_date}.")


def load_capture(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != capture.SCHEMA or payload.get("model_identity") != MODEL_IDENTITY:
        raise ValueError("Capture identity is invalid.")
    if payload.get("predeclaration_sha256") != capture.PREDECLARATION_SHA256 or payload.get("stations_sha256") != capture.STATIONS_SHA256:
        raise ValueError("Capture is not bound to the frozen predeclaration.")
    if payload.get("research_only") is not True or payload.get("active_trading_capability_changed") is not False:
        raise ValueError("Capture has an authorizing identity.")
    if (
        payload.get("production_database_accessed") is not False
        or payload.get("historical_price_data_inspected") is not False
        or payload.get("credential_required") is not False
    ):
        raise ValueError("Capture accessed prohibited state.")
    if payload.get("request_policy") != {
        "no_retry": True,
        "stop_on_http_429": True,
        "maximum_requests": 23,
        "actual_network_requests": 23,
    }:
        raise ValueError("Capture request identity is invalid.")
    design = payload.get("design", {})
    coverage = payload.get("coverage", {})
    if design != {
        "forecast_model": capture.FORECAST_MODEL,
        "source_model": capture.SOURCE_MODEL,
        "forecast_runtime_utc": "12:00:00",
        "forecast_available_by_utc": "20:00:00",
        "duplicate_policy": "collapse_only_identical_semantic_selected_row",
        "selected_exact_duplicates_per_station": capture.EXPECTED_EXACT_DUPLICATES_PER_STATION,
        "global_optional_schema_required": capture.REQUIRE_GLOBAL_OPTIONAL_SCHEMA,
        "calibration_first_date": "2021-02-15",
        "calibration_last_date": "2021-07-09",
        "calibration_dates": 145,
        "evaluation_first_date": "2021-07-10",
        "evaluation_last_date": "2022-03-16",
        "evaluation_dates": 250,
        "station_count": 20,
    }:
        raise ValueError("Capture design identity is invalid.")
    if (
        not isinstance(coverage, dict)
        or coverage.get("requested_dates") != 395
        or coverage.get("complete_dates") != 395
        or coverage.get("station_dates") != 7900
    ):
        raise ValueError("Capture coverage is incomplete.")
    forecast_sources = payload.get("forecast_sources")
    station_identities = payload.get("station_identities")
    validate_duplicate_counts(coverage, forecast_sources)
    station_path = Path(capture.__file__).with_name("stations.json")
    if capture.file_sha256(station_path) != capture.STATIONS_SHA256:
        raise ValueError("Frozen station inventory hash is invalid.")
    expected_station_ids = {
        row["station_id"] for row in json.loads(station_path.read_text(encoding="utf-8"))
    }
    if (
        not isinstance(forecast_sources, list)
        or not isinstance(station_identities, list)
        or len(forecast_sources) != 20
        or any(not isinstance(source, dict) for source in forecast_sources)
        or any(not isinstance(identity, dict) for identity in station_identities)
        or {source.get("station_id") for source in forecast_sources}
        != expected_station_ids
        or {row.get("station_id") for row in station_identities} != expected_station_ids
        or any(source.get("url") != capture.mos_url(str(source.get("station_id"))) for source in forecast_sources)
        or any(not is_sha256(source.get("sha256")) for source in forecast_sources)
        or (
            capture.REQUIRE_GLOBAL_OPTIONAL_SCHEMA
            and len({tuple(source.get("csv_fields", [])) for source in forecast_sources}) != 1
        )
        or any(not capture.REQUIRED_MOS_FIELDS.issubset(source.get("csv_fields", [])) for source in forecast_sources)
    ):
        raise ValueError("Capture duplicate identity is invalid.")
    calibration_dates, evaluation_dates = capture.frozen_dates()
    outcome_sources = payload.get("outcome_sources")
    if (
        not isinstance(outcome_sources, list)
        or len(outcome_sources) != 3
        or any(not isinstance(source, dict) for source in outcome_sources)
        or outcome_sources[0].get("url") != capture.ISD_URL
        or outcome_sources[1].get("label") != "calibration"
        or outcome_sources[1].get("url")
        != capture.outcome_url(station_identities, calibration_dates[0], calibration_dates[-1])
        or outcome_sources[2].get("label") != "evaluation"
        or outcome_sources[2].get("url")
        != capture.outcome_url(station_identities, evaluation_dates[0], evaluation_dates[-1])
        or any(not is_sha256(source.get("sha256")) for source in outcome_sources)
        or any(not isinstance(source.get("headers"), dict) for source in outcome_sources)
    ):
        raise ValueError("Capture outcome source identity is invalid.")
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 7900 or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Capture rows are incomplete.")
    expected_identities = {
        (station, market_date)
        for station in expected_station_ids
        for market_date in calibration_dates + evaluation_dates
    }
    identities = {(row.get("station_id"), row.get("market_date")) for row in rows}
    if identities != expected_identities:
        raise ValueError("Capture station/date identity is incomplete or duplicated.")
    for row in rows:
        validate_capture_row(row)
    return payload


def wilson_lower(successes: int, count: int) -> Decimal:
    if count != 120 or successes < 0 or successes > count:
        raise ValueError("Frozen Wilson inputs are invalid.")
    n = Decimal(count)
    proportion = Decimal(successes) / n
    z2 = Z90 * Z90
    center = proportion + z2 / (Decimal(2) * n)
    radius = Z90 * ((proportion * (Decimal(1) - proportion) + z2 / (Decimal(4) * n)) / n).sqrt()
    lower = (center - radius) / (Decimal(1) + z2 / n)
    return max(Decimal(0), lower).quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)


def boundaries(forecast: Decimal) -> list[Decimal]:
    first_integer = math.ceil(float(forecast + Decimal("4.0") - Decimal("0.5")))
    boundary = Decimal(first_integer) + Decimal("0.5")
    output = []
    while boundary - forecast < Decimal("8.0"):
        if boundary - forecast >= Decimal("4.0"):
            output.append(boundary)
        boundary += Decimal("1.0")
    return output


def distance_bin(distance: Decimal) -> str:
    for low in range(4, 8):
        if Decimal(low) <= distance < Decimal(low + 1):
            return f"{low}-{low + 1}"
    raise ValueError("Distance is outside the frozen interval.")


def calibration_climatology(rows: list[dict[str, object]]) -> dict[str, Decimal]:
    totals: dict[str, list[int]] = {key: [0, 0] for key in ("4-5", "5-6", "6-7", "7-8")}
    for row in rows:
        forecast = Decimal(str(row["forecast_high_f"]))
        observed = Decimal(str(row["observed_high_f"]))
        for boundary in boundaries(forecast):
            key = distance_bin(boundary - forecast)
            totals[key][1] += 1
            totals[key][0] += int(observed <= boundary)
    output = {}
    for key, (wins, count) in totals.items():
        if count != 2900:
            raise ValueError(f"Calibration climatology has wrong count for {key}: {count}.")
        output[key] = (Decimal(wins) + Decimal("0.5")) / (Decimal(count) + Decimal(1))
    return output


def split_rows(payload: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    calibration_dates, evaluation_dates = capture.frozen_dates()
    calibration_set = set(calibration_dates)
    evaluation_set = set(evaluation_dates)
    calibration_rows = [row for row in payload["rows"] if row["market_date"] in calibration_set]
    evaluation_rows = [row for row in payload["rows"] if row["market_date"] in evaluation_set]
    if len(calibration_rows) != 2900 or len(evaluation_rows) != 5000:
        raise ValueError("Capture split is incomplete.")
    return calibration_rows, evaluation_rows


def build_predictions(calibration_rows: list[dict[str, object]], evaluation_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    all_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in calibration_rows + evaluation_rows:
        all_rows[str(row["station_id"])].append(row)
    for rows in all_rows.values():
        rows.sort(key=lambda row: str(row["market_date"]))
    predictions = []
    for row in sorted(evaluation_rows, key=lambda value: (str(value["market_date"]), str(value["station_id"]))):
        station = str(row["station_id"])
        market_date = dt.date.fromisoformat(str(row["market_date"]))
        cutoff = (market_date - dt.timedelta(days=2)).isoformat()
        causal = [candidate for candidate in all_rows[station] if str(candidate["market_date"]) <= cutoff]
        history = causal[-120:]
        if len(history) != 120:
            raise ValueError(f"Rolling history is not exactly 120 for {station}|{market_date}.")
        history_dates = [str(candidate["market_date"]) for candidate in history]
        if len(set(history_dates)) != 120 or history_dates[-1] != cutoff:
            raise ValueError(f"Rolling history has a date gap for {station}|{market_date}.")
        residuals = [Decimal(str(candidate["residual_f"])) for candidate in history]
        forecast = Decimal(str(row["forecast_high_f"]))
        observed = Decimal(str(row["observed_high_f"]))
        for boundary in boundaries(forecast):
            residual_boundary = boundary - forecast
            successes = sum(residual <= residual_boundary for residual in residuals)
            score = wilson_lower(successes, 120)
            if score < Decimal("0.9000"):
                continue
            predictions.append({
                "station_id": station,
                "market_date": market_date.isoformat(),
                "forecast_high_f": str(forecast),
                "observed_high_f": str(observed),
                "boundary_f": str(boundary),
                "distance_f": str(boundary - forecast),
                "distance_bin": distance_bin(boundary - forecast),
                "history_first_date": history_dates[0],
                "history_last_date": history_dates[-1],
                "history_count": 120,
                "history_successes": successes,
                "score": str(score),
                "outcome": int(observed <= boundary),
            })
    return predictions


def clustered_lower(rows: list[dict[str, object]], tail: float, excluded_station: str | None = None) -> Decimal | None:
    clusters: dict[str, list[Decimal]] = defaultdict(list)
    for row in rows:
        if excluded_station is not None and row["station_id"] == excluded_station:
            continue
        clusters[str(row["market_date"])].append(Decimal(row["outcome"]) - Decimal(str(row["score"])))
    ordered = [clusters[key] for key in sorted(clusters)]
    if not ordered:
        return None
    state = 0x5A17C9E3
    means = []
    for _ in range(BOOTSTRAP_SAMPLES):
        total = Decimal(0)
        count = 0
        for _ in range(len(ordered)):
            state = (state * 1_664_525 + 1_013_904_223) & 0xFFFFFFFF
            cluster = ordered[(state * len(ordered)) // 0x1_0000_0000]
            total += sum(cluster, Decimal(0))
            count += len(cluster)
        means.append(float(total / Decimal(count)))
    means.sort()
    return Decimal(str(means[math.floor((BOOTSTRAP_SAMPLES - 1) * tail)]))


def evaluate(payload: dict[str, object]) -> dict[str, object]:
    calibration_rows, evaluation_rows = split_rows(payload)
    climatology = calibration_climatology(calibration_rows)
    selected = build_predictions(calibration_rows, evaluation_rows)
    selected_dates = {str(row["market_date"]) for row in selected}
    station_counts: dict[str, int] = defaultdict(int)
    station_dates: dict[str, set[str]] = defaultdict(set)
    date_counts: dict[str, int] = defaultdict(int)
    for row in selected:
        station = str(row["station_id"])
        market_date = str(row["market_date"])
        station_counts[station] += 1
        station_dates[station].add(market_date)
        date_counts[market_date] += 1
    model_brier = sum((Decimal(row["score"]) - Decimal(row["outcome"])) ** 2 for row in selected) / Decimal(len(selected)) if selected else Decimal(0)
    reference_brier = sum((climatology[str(row["distance_bin"])] - Decimal(row["outcome"])) ** 2 for row in selected) / Decimal(len(selected)) if selected else Decimal(0)
    brier_skill = Decimal(1) - model_brier / reference_brier if reference_brier > 0 else Decimal("-Infinity")
    band_results = []
    for low, high, label in BANDS:
        rows = [row for row in selected if low <= Decimal(row["score"]) < high]
        dates = {str(row["market_date"]) for row in rows}
        observed = sum((Decimal(row["outcome"]) for row in rows), Decimal(0)) / Decimal(len(rows)) if rows else None
        mean_score = sum((Decimal(row["score"]) for row in rows), Decimal(0)) / Decimal(len(rows)) if rows else None
        error = abs(observed - mean_score) if observed is not None and mean_score is not None else None
        band_results.append({
            "band": label,
            "rows": len(rows),
            "independent_dates": len(dates),
            "observed": f"{observed:.6f}" if observed is not None else None,
            "mean_score": f"{mean_score:.6f}" if mean_score is not None else None,
            "absolute_error": f"{error:.6f}" if error is not None else None,
            "passes": len(dates) >= 30 and error is not None and error <= Decimal("0.05"),
        })
    lower90 = clustered_lower(selected, 0.10)
    lower95 = clustered_lower(selected, 0.05)
    stations = sorted({str(row["station_id"]) for row in evaluation_rows})
    holdouts = []
    for station in stations:
        lower = clustered_lower(selected, 0.05, station)
        holdouts.append({
            "excluded_station_id": station,
            "lower_95_observed_minus_score": f"{lower:.6f}" if lower is not None else None,
            "passes": lower is not None and lower >= 0,
        })
    maximum_station_share = Decimal(max(station_counts.values(), default=0)) / Decimal(len(selected)) if selected else Decimal(1)
    maximum_date_share = Decimal(max(date_counts.values(), default=0)) / Decimal(len(selected)) if selected else Decimal(1)
    station_date_counts = {station: len(station_dates[station]) for station in stations}
    gates = {
        "all_250_evaluation_dates_selected": len(selected_dates) == 250,
        "positive_brier_skill": brier_skill.is_finite() and brier_skill > 0,
        "every_reliability_band_passes": len(band_results) == 3 and all(result["passes"] for result in band_results),
        "date_clustered_90_margin_nonnegative": lower90 is not None and lower90 >= 0,
        "date_clustered_95_margin_nonnegative": lower95 is not None and lower95 >= 0,
        "every_station_holdout_clustered_95_passes": len(holdouts) == 20 and all(result["passes"] for result in holdouts),
        "every_station_has_30_dates": len(station_date_counts) == 20 and all(count >= 30 for count in station_date_counts.values()),
        "station_concentration": maximum_station_share <= Decimal("0.10"),
        "date_concentration": maximum_date_share <= Decimal("0.02"),
    }
    return {
        "selected_predictions": len(selected),
        "selected_independent_dates": len(selected_dates),
        "selected_station_count": len(station_counts),
        "mean_score": f"{sum((Decimal(row['score']) for row in selected), Decimal(0)) / Decimal(len(selected)):.6f}" if selected else None,
        "observed_success": f"{sum((Decimal(row['outcome']) for row in selected), Decimal(0)) / Decimal(len(selected)):.6f}" if selected else None,
        "model_brier": f"{model_brier:.6f}" if selected else None,
        "reference_brier": f"{reference_brier:.6f}" if selected else None,
        "brier_skill": f"{brier_skill:.6f}" if brier_skill.is_finite() else None,
        "lower_90_observed_minus_score": f"{lower90:.6f}" if lower90 is not None else None,
        "lower_95_observed_minus_score": f"{lower95:.6f}" if lower95 is not None else None,
        "maximum_station_share": f"{maximum_station_share:.6f}",
        "maximum_date_share": f"{maximum_date_share:.6f}",
        "station_independent_dates": station_date_counts,
        "calibration_climatology": {key: f"{value:.6f}" for key, value in climatology.items()},
        "reliability_bands": band_results,
        "station_holdouts": holdouts,
        "gates": gates,
        "passes": all(gates.values()),
        "failed_gates": [key for key, passed in gates.items() if not passed],
        "predictions": selected,
    }


def main() -> None:
    args = parse_args()
    capture_path = Path(args.capture).resolve()
    payload = load_capture(capture_path)
    result = evaluate(payload)
    report = {
        "schema": SCHEMA,
        "model_identity": MODEL_IDENTITY,
        "predeclaration_sha256": capture.PREDECLARATION_SHA256,
        "research_only": True,
        "active_trading_capability_changed": False,
        "historical_price_data_inspected": False,
        "capture_sha256": file_sha256(capture_path),
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "evaluation": result,
    }
    Path(args.output).write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({
        "passes": result["passes"],
        "failed_gates": result["failed_gates"],
        "selected_predictions": result["selected_predictions"],
        "selected_independent_dates": result["selected_independent_dates"],
        "brier_skill": result["brier_skill"],
        "lower_90_observed_minus_score": result["lower_90_observed_minus_score"],
        "lower_95_observed_minus_score": result["lower_95_observed_minus_score"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
