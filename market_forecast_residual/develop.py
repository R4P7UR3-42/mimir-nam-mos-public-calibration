#!/usr/bin/env python3
"""Training-only market plus exact-run ECMWF residual development."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import urllib.parse
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from market_implied import evaluate as market  # noqa: E402


IDENTITY = "daily_high_top_tail_market_ecmwf_residual_18z_development_v1"
SCHEMA = "daily_high_top_tail_market_ecmwf_residual_18z_development_v1"
DEVELOPMENT_SHA256 = "f7f04d1b85e7cf00b8d8eeb0f5a3e589e9fb60fc36bfd84d369b30b7aafe0940"
STATIONS_SHA256 = "c0a6c863e94a8255dcf63cc3ea07eb7576ace7207f318372907abbf780b2f7b7"
START = dt.date(2026, 2, 11)
END = dt.date(2026, 3, 19)
MIN_PRICE = Decimal("0.5000")
MAX_PRICE = Decimal("0.9700")
RIDGE = 0.1
MODEL_ORDER = ("market_offset", "market_free", "forecast_only")
FORECAST_BASE = "https://single-runs-api.open-meteo.com/v1/forecast"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    return parser.parse_args()


def load_stations(path: Path) -> list[dict[str, object]]:
    if market.file_sha256(path) != STATIONS_SHA256:
        raise ValueError("Training station inventory hash is invalid.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"station_id", "series_ticker", "latitude", "longitude", "time_zone"}
    if (
        not isinstance(payload, list)
        or len(payload) != 10
        or any(not isinstance(row, dict) or set(row) != required for row in payload)
        or len({row["station_id"] for row in payload}) != 10
        or len({row["series_ticker"] for row in payload}) != 10
    ):
        raise ValueError("Training station inventory is malformed.")
    for row in payload:
        if not str(row["series_ticker"]).startswith("KXHIGH"):
            raise ValueError("Training series identity is malformed.")
        ZoneInfo(str(row["time_zone"]))
    return payload


def forecast_run(market_date: dt.date) -> dt.datetime:
    return dt.datetime.combine(market_date - dt.timedelta(days=1), dt.time(6), tzinfo=dt.timezone.utc)


def fetch_forecast(
    client: market.PublicClient,
    station: dict[str, object],
    market_date: dt.date,
) -> dict[str, object]:
    run = forecast_run(market_date)
    query = {
        "latitude": str(station["latitude"]),
        "longitude": str(station["longitude"]),
        "hourly": "temperature_2m",
        "temperature_unit": "fahrenheit",
        "timezone": "UTC",
        "models": "ecmwf_ifs",
        "run": run.strftime("%Y-%m-%dT%H:%M"),
        "forecast_hours": "96",
    }
    url = f"{FORECAST_BASE}?{urllib.parse.urlencode(query)}"
    label = f"training-{station['series_ticker']}-{market_date.isoformat()}-ecmwf-06z"
    payload = client.fetch(url, label)
    if (
        payload.get("utc_offset_seconds") != 0
        or payload.get("timezone") != "GMT"
        or not isinstance(payload.get("hourly_units"), dict)
        or payload["hourly_units"].get("temperature_2m") != "°F"
        or not isinstance(payload.get("hourly"), dict)
    ):
        raise ValueError(f"Forecast identity is invalid for {label}.")
    latitude = market.decimal_value(payload.get("latitude"), "forecast latitude")
    longitude = market.decimal_value(payload.get("longitude"), "forecast longitude")
    if (
        abs(latitude - Decimal(str(station["latitude"]))) > Decimal("0.1")
        or abs(longitude - Decimal(str(station["longitude"]))) > Decimal("0.1")
    ):
        raise ValueError(f"Forecast grid identity is too distant for {label}.")
    hourly = payload["hourly"]
    times = hourly.get("time")
    values = hourly.get("temperature_2m")
    if not isinstance(times, list) or not isinstance(values, list) or len(times) != len(values) or len(times) != 96:
        raise ValueError(f"Forecast hourly coverage is malformed for {label}.")
    zone = ZoneInfo(str(station["time_zone"]))
    selected: list[Decimal] = []
    selected_times: list[str] = []
    for timestamp, value in zip(times, values, strict=True):
        if not isinstance(timestamp, str) or value is None:
            continue
        try:
            instant = dt.datetime.fromisoformat(timestamp).replace(tzinfo=dt.timezone.utc)
        except ValueError as error:
            raise ValueError(f"Forecast timestamp is malformed for {label}.") from error
        if instant.astimezone(zone).date() == market_date:
            selected.append(market.decimal_value(value, "forecast temperature"))
            selected_times.append(timestamp)
    if len(selected) not in (23, 24, 25):
        raise ValueError(f"Forecast local-day coverage is incomplete for {label}: {len(selected)} hours.")
    return {
        "forecast_model": "ecmwf_ifs",
        "forecast_run": run.isoformat().replace("+00:00", "Z"),
        "forecast_available_buffer_hours": 6,
        "forecast_max_f": str(max(selected)),
        "forecast_local_hour_count": len(selected),
        "forecast_first_utc": selected_times[0] + "Z",
        "forecast_last_utc": selected_times[-1] + "Z",
        "forecast_grid_latitude": str(latitude),
        "forecast_grid_longitude": str(longitude),
        "forecast_source_url": url,
    }


def usable_row(
    client: market.PublicClient,
    station: dict[str, object],
    market_date: dt.date,
    top: dict[str, object],
) -> dict[str, object]:
    quote = market.capture_quote(client, str(station["series_ticker"]), market_date, top, "training")
    forecast = fetch_forecast(client, station, market_date)
    threshold = market.decimal_value(top.get("floor_strike"), "top threshold")
    base = {
        **quote,
        **forecast,
        "station_id": station["station_id"],
        "time_zone": station["time_zone"],
        "threshold_f": str(threshold),
    }
    if quote.get("no_limit") is None:
        return {**base, "model_candidate": False, "model_reason": quote["reason"]}
    price = market.decimal_value(quote["no_limit"], "NO limit")
    if price < MIN_PRICE or price > MAX_PRICE:
        return {**base, "model_candidate": False, "model_reason": "outside_development_price_range"}
    forecast_max = market.decimal_value(forecast["forecast_max_f"], "forecast maximum")
    return {
        **base,
        "model_candidate": True,
        "model_reason": "eligible_training_row",
        "no_limit": str(price),
        "fee": str(market.fee(price)),
        "forecast_distance_f": str(threshold - forecast_max),
    }


def sigmoid(value: float) -> float:
    if value >= 0:
        exp = math.exp(-value)
        return 1.0 / (1.0 + exp)
    exp = math.exp(value)
    return exp / (1.0 + exp)


def clipped_probability(value: float) -> float:
    return min(0.999, max(0.001, value))


def logit(value: float) -> float:
    value = min(0.999999, max(0.000001, value))
    return math.log(value / (1.0 - value))


def design(row: dict[str, object], name: str) -> tuple[float, list[float]]:
    price_logit = logit(float(row["no_limit"]))
    distance = float(row["forecast_distance_f"]) / 5.0
    if name == "market_offset":
        return price_logit, [1.0, distance]
    if name == "market_free":
        return 0.0, [1.0, price_logit, distance]
    if name == "forecast_only":
        return 0.0, [1.0, distance]
    raise ValueError(f"Unknown model {name}.")


def solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [matrix[index][:] + [vector[index]] for index in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Logistic Hessian is singular.")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][index] - factor * augmented[column][index]
                for index in range(size + 1)
            ]
    return [augmented[index][-1] for index in range(size)]


def fit(rows: list[dict[str, object]], name: str) -> list[float]:
    if not rows:
        raise ValueError("Cannot fit an empty model.")
    dimension = len(design(rows[0], name)[1])
    coefficients = [0.0] * dimension
    for _ in range(100):
        gradient = [0.0] * dimension
        hessian = [[0.0] * dimension for _ in range(dimension)]
        for row in rows:
            offset, features = design(row, name)
            probability = sigmoid(offset + sum(value * coefficient for value, coefficient in zip(features, coefficients)))
            residual = probability - int(row["outcome_no"])
            weight = max(1e-9, probability * (1.0 - probability))
            for left in range(dimension):
                gradient[left] += features[left] * residual
                for right in range(dimension):
                    hessian[left][right] += features[left] * features[right] * weight
        for index in range(1, dimension):
            gradient[index] += RIDGE * coefficients[index]
            hessian[index][index] += RIDGE
        hessian[0][0] += 1e-9
        step = solve(hessian, gradient)
        coefficients = [value - change for value, change in zip(coefficients, step)]
        if max(abs(value) for value in step) < 1e-10:
            break
    return coefficients


def predict(row: dict[str, object], name: str, coefficients: list[float]) -> float:
    offset, features = design(row, name)
    return clipped_probability(sigmoid(offset + sum(value * coefficient for value, coefficient in zip(features, coefficients))))


def model_report(rows: list[dict[str, object]], name: str) -> dict[str, object]:
    dates = sorted({str(row["market_date"]) for row in rows})
    oof: list[dict[str, object]] = []
    for market_date in dates:
        training = [row for row in rows if row["market_date"] != market_date]
        holdout = [row for row in rows if row["market_date"] == market_date]
        coefficients = fit(training, name)
        oof.extend({**row, "score": predict(row, name, coefficients)} for row in holdout)
    count = len(oof)
    brier = sum((float(row["score"]) - int(row["outcome_no"])) ** 2 for row in oof) / count
    baseline_brier = sum((float(row["no_limit"]) - int(row["outcome_no"])) ** 2 for row in oof) / count
    log_loss = -sum(
        int(row["outcome_no"]) * math.log(float(row["score"]))
        + (1 - int(row["outcome_no"])) * math.log(1 - float(row["score"]))
        for row in oof
    ) / count
    baseline_log_loss = -sum(
        int(row["outcome_no"]) * math.log(float(row["no_limit"]))
        + (1 - int(row["outcome_no"])) * math.log(1 - float(row["no_limit"]))
        for row in oof
    ) / count
    calibration_error = abs(sum(float(row["score"]) for row in oof) / count - sum(int(row["outcome_no"]) for row in oof) / count)
    station_fits = []
    coefficient_signs_pass = True
    for station in sorted({str(row["series_ticker"]) for row in rows}):
        coefficients = fit([row for row in rows if row["series_ticker"] != station], name)
        distance_index = 2 if name == "market_free" else 1
        passes = coefficients[distance_index] > 0 and (name != "market_free" or coefficients[1] > 0)
        coefficient_signs_pass = coefficient_signs_pass and passes
        station_fits.append({"excluded_series_ticker": station, "coefficients": coefficients, "passes": passes})
    gates = {
        "minimum_rows": len(rows) >= 100,
        "minimum_dates": len(dates) >= 30,
        "minimum_stations": len({str(row["series_ticker"]) for row in rows}) >= 8,
        "positive_brier_skill": baseline_brier > 0 and 1 - brier / baseline_brier > 0,
        "positive_log_loss_improvement": baseline_log_loss - log_loss > 0,
        "calibration_error_at_most_003": calibration_error <= 0.03,
        "leave_one_station_out_coefficient_signs": coefficient_signs_pass,
    }
    final_coefficients = fit(rows, name)
    return {
        "name": name,
        "rows": len(rows),
        "dates": len(dates),
        "stations": len({str(row["series_ticker"]) for row in rows}),
        "oof_brier": f"{brier:.10f}",
        "displayed_price_brier": f"{baseline_brier:.10f}",
        "oof_brier_skill": f"{1 - brier / baseline_brier:.10f}" if baseline_brier > 0 else None,
        "oof_log_loss": f"{log_loss:.10f}",
        "displayed_price_log_loss": f"{baseline_log_loss:.10f}",
        "oof_log_loss_improvement": f"{baseline_log_loss - log_loss:.10f}",
        "oof_calibration_error": f"{calibration_error:.10f}",
        "final_coefficients": final_coefficients,
        "station_holdout_fits": station_fits,
        "gates": gates,
        "admissible": all(gates.values()),
    }


def main() -> None:
    args = parse_args()
    market.assert_not_production_host()
    root = Path(__file__).resolve().parent
    if market.file_sha256(root / "DEVELOPMENT.md") != DEVELOPMENT_SHA256:
        raise ValueError("Development freeze hash is invalid.")
    stations = load_stations(root / "training_stations.json")
    if args.max_requests != market.NETWORK_LIMIT:
        raise ValueError(f"The exact request ceiling is {market.NETWORK_LIMIT}.")
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    client = market.PublicClient(output, args.max_requests)
    cutoff = market.validate_historical_cutoff(client)
    fee_identities = [market.validate_fee_identity(client, str(row["series_ticker"]), "training") for row in stations]
    rows: list[dict[str, object]] = []
    for station in stations:
        ticker = str(station["series_ticker"])
        markets = market.discover_top_markets(client, ticker, START, END, "training", True)
        for market_date in sorted(markets):
            rows.append(usable_row(client, station, market_date, markets[market_date]))
            print(json.dumps({
                "series_ticker": ticker,
                "market_date": market_date.isoformat(),
                "network_requests": client.used,
            }, sort_keys=True), flush=True)
    candidates = [row for row in rows if row.get("model_candidate") is True]
    reports = [model_report(candidates, name) for name in MODEL_ORDER]
    admissible = [row for row in reports if row["admissible"]]
    selected = min(admissible, key=lambda row: (float(row["oof_brier"]), MODEL_ORDER.index(str(row["name"])))) if admissible else None
    report = {
        "schema": SCHEMA,
        "identity": IDENTITY,
        "research_only": True,
        "training_only": True,
        "evaluation_series_accessed": False,
        "production_database_accessed": False,
        "active_trading_capability_changed": False,
        "development_sha256": DEVELOPMENT_SHA256,
        "training_stations_sha256": STATIONS_SHA256,
        "historical_cutoff": cutoff,
        "network_requests": client.used,
        "captured_rows": len(rows),
        "eligible_rows": len(candidates),
        "eligible_dates": len({str(row["market_date"]) for row in candidates}),
        "eligible_stations": len({str(row["series_ticker"]) for row in candidates}),
        "models": reports,
        "selected_model": selected,
        "successor_freeze_permitted": selected is not None,
        "initial_evidence_passes": False,
        "scale_evidence_passes": False,
        "fee_identities": fee_identities,
        "rows": rows,
    }
    market.atomic_json(output / "development.json", report)
    print(json.dumps({key: report[key] for key in (
        "schema", "network_requests", "captured_rows", "eligible_rows", "selected_model",
        "successor_freeze_permitted",
    )}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
