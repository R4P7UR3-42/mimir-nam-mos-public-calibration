#!/usr/bin/env python3
"""Frozen station-robust NBM Q75 midnight split development audit."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TIME_ROOT = ROOT.parent / "nbm_q90_time"
SPEC = importlib.util.spec_from_file_location("nbm_q90_time_v2", TIME_ROOT / "evaluate.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load the frozen Q90 time source module.")
time_model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(time_model)
price = time_model.price

SCHEMA = "noaa_nbm_v5_q75_station_robust_midnight_split_evaluation_v1"
IDENTITY = "noaa_nbm_v5_q75_station_robust_midnight_split_development_v1"
PREDECLARATION_SHA256 = "564b72e864570eb6a4d857e42d3c9630666c2b798521fc835aa6d212f4a26e4c"
TRAINING_START = dt.date(2026, 5, 8)
TRAINING_END = dt.date(2026, 6, 26)
HELD_OUT_START = dt.date(2026, 6, 27)
HELD_OUT_END = dt.date(2026, 8, 14)
MIN_PRICE = Decimal("0.50")
MAX_PRICE = Decimal("0.85")
MIN_EDGE = Decimal("0.0150")
MIN_TRAINING_SCORE = Decimal("0.7500")
MIDNIGHT_CLOCK = time_model.CLOCKS[3]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    return parser.parse_args()


def load_q75_rows() -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    price_root = time_model.PRICE_ROOT
    station_rows, station_map = price.load_station_map(price_root / "station_series.json")
    parent = price.load_parent_rows(price_root, station_map)
    parent_by_key = {(str(row["station_id"]), str(row["market_date"])): row for row in parent}
    q75_by_key = {}
    for filename, expected_hash in price.INPUT_SHA256.items():
        path = price_root.parent / "nbm_qmd" / "inputs" / filename
        if price.file_sha256(path) != expected_hash:
            raise ValueError(f"Parent input hash is invalid: {filename}.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload["rows"]:
            market_date = str(row["market_date"])
            if market_date == price.PARENT_START.isoformat():
                continue
            matches = [
                percentile for percentile in row["percentiles"]
                if percentile.get("probability") == "0.75"
            ]
            if len(matches) != 1:
                raise ValueError("Parent Q75 percentile identity is invalid.")
            q75 = price.decimal_value(matches[0].get("max_f"), "Q75")
            if q75 != q75.to_integral_value():
                raise ValueError("Parent Q75 value is not an exact integer.")
            key = (str(row["station_id"]), market_date)
            if key in q75_by_key:
                raise ValueError("Parent Q75 station/date is duplicated.")
            q75_by_key[key] = str(q75)
    if set(q75_by_key) != set(parent_by_key):
        raise ValueError("Parent Q75 coverage does not match the frozen 99-date window.")
    rows = [{**row, "q75_f": q75_by_key[key]} for key, row in parent_by_key.items()]
    rows.sort(key=lambda row: (str(row["market_date"]), str(row["station_id"])))
    return rows, station_rows


def derive_training_score(rows: list[dict[str, object]]) -> dict[str, object]:
    training = []
    for row in rows:
        market_date = dt.date.fromisoformat(str(row["market_date"]))
        if TRAINING_START <= market_date <= TRAINING_END:
            training.append({
                **row,
                "outcome_no": int(
                    price.decimal_value(row["observed_high_f"], "observed high")
                    <= price.decimal_value(row["q75_f"], "Q75")
                ),
            })
    dates = {str(row["market_date"]) for row in training}
    stations = {str(row["station_id"]) for row in training}
    if len(training) != 1_000 or len(dates) != 50 or len(stations) != 20:
        raise ValueError("Q75 training coverage is not exact 50 dates by 20 stations.")
    global_lower = price.clustered_lower(training, "outcome_no", 0.10, 0x075A11CE)
    if global_lower is None:
        raise ValueError("Q75 global clustered training score is unavailable.")
    holdouts = []
    candidates = [global_lower]
    for station in sorted(stations):
        remainder = [row for row in training if row["station_id"] != station]
        lower = price.clustered_lower(remainder, "outcome_no", 0.10, 0x075A11CE)
        if lower is None:
            raise ValueError("Q75 station holdout score is unavailable.")
        candidates.append(lower)
        holdouts.append({
            "excluded_station_id": station,
            "lower_90_success": f"{lower:.8f}",
        })
    score = min(candidates).quantize(Decimal("0.0001"), rounding=ROUND_FLOOR)
    observed = sum((Decimal(row["outcome_no"]) for row in training), Decimal(0)) / Decimal(len(training))
    return {
        "rows": len(training),
        "independent_dates": len(dates),
        "stations": len(stations),
        "observed_success_rate": f"{observed:.8f}",
        "global_lower_90_success": f"{global_lower:.8f}",
        "station_holdouts": holdouts,
        "frozen_score": f"{score:.4f}",
        "passes_minimum_score": score >= MIN_TRAINING_SCORE,
    }


def exact_q75_market(
    station_row: dict[str, object], event_markets: list[dict[str, object]]
) -> dict[str, object] | None:
    q75 = price.decimal_value(station_row["q75_f"], "Q75")
    matches = [
        market for market in event_markets
        if market.get("strike_type") == "greater"
        and market.get("floor_strike") is not None
        and price.decimal_value(market["floor_strike"], "floor strike") == q75
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"Exact Q75 greater contract is ambiguous for {station_row['series_ticker']}.")
    market = matches[0]
    outcome_no = price.decimal_value(station_row["observed_high_f"], "observed high") <= q75
    if (
        q75 != q75.to_integral_value()
        or market.get("market_type") != "binary"
        or market.get("cap_strike") is not None
        or market.get("result") not in ("yes", "no")
        or market.get("yes_sub_title") != f"{int(q75) + 1}° or above"
        or (market.get("result") == "no") != outcome_no
        or ("is_provisional" in market and market["is_provisional"] is not False)
        or ("mve_collection_ticker" in market and market["mve_collection_ticker"] not in (None, ""))
        or ("fee_waiver_expiration_time" in market and market["fee_waiver_expiration_time"] is not None)
    ):
        raise ValueError(f"Exact Q75 contract identity is invalid for {market.get('ticker')}.")
    return market


def apply_score(row: dict[str, object], score: Decimal) -> dict[str, object]:
    if row.get("no_limit") is None:
        return row
    no_limit = price.decimal_value(row["no_limit"], "NO limit")
    exact_fee = price.fee(no_limit)
    edge = score - no_limit - exact_fee
    eligible = MIN_PRICE <= no_limit <= MAX_PRICE and edge >= MIN_EDGE
    return {
        **row,
        "candidate": eligible,
        "reason": "eligible_quote" if eligible else "price_or_edge_outside_policy",
        "fee": str(exact_fee),
        "conservative_probability": f"{score:.4f}",
        "conservative_edge": f"{edge:.8f}",
    }


def held_out_metrics(rows: list[dict[str, object]], score: Decimal) -> dict[str, object]:
    original = price.PROBABILITY
    try:
        price.PROBABILITY = score
        return time_model.held_out_diagnostic(rows)
    finally:
        price.PROBABILITY = original


def main() -> None:
    args = parse_args()
    price.assert_not_production_host()
    if price.file_sha256(ROOT / "PREDECLARATION.md") != PREDECLARATION_SHA256:
        raise ValueError("Frozen Q75 predeclaration hash is invalid.")
    rows, stations = load_q75_rows()
    training = derive_training_score(rows)
    score = Decimal(str(training["frozen_score"]))
    if not training["passes_minimum_score"]:
        raise ValueError("Q75 station-robust training score is below exact 0.7500.")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    client = time_model.ResilientPublicClient(output_dir, args.max_requests)
    fee_identities = [price.validate_fee_identity(client, row["series_ticker"]) for row in stations]
    cutoffs = price.historical_cutoffs(client)
    rows_by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        market_date = dt.date.fromisoformat(str(row["market_date"]))
        if HELD_OUT_START <= market_date <= HELD_OUT_END:
            rows_by_station[str(row["station_id"])].append(row)
    quote_rows = []
    exact_contracts = 0
    for station in stations:
        station_id = station["station_id"]
        markets_by_date = price.discover_markets(client, station["series_ticker"])
        for station_row in sorted(rows_by_station[station_id], key=lambda row: str(row["market_date"])):
            market_date = dt.date.fromisoformat(str(station_row["market_date"]))
            market = exact_q75_market(station_row, markets_by_date.get(market_date, []))
            if market is None:
                quote_rows.append({
                    **station_row,
                    "clock_id": MIDNIGHT_CLOCK["id"],
                    "candidate": False,
                    "reason": "no_exact_q75_greater_contract",
                })
                continue
            exact_contracts += 1
            quote_rows.append(apply_score(
                time_model.capture_at(client, station_row, market, MIDNIGHT_CLOCK), score,
            ))
            print(json.dumps({
                "station_id": station_id,
                "market_date": station_row["market_date"],
                "network_requests": client.used,
            }, sort_keys=True), flush=True)
    selections = time_model.select_rows(
        quote_rows, str(MIDNIGHT_CLOCK["id"]), HELD_OUT_START, HELD_OUT_END,
    )
    filled = time_model.attach_trades(client, selections, cutoffs["trades_created_ts"])
    evaluation = held_out_metrics(filled, score)
    report = {
        "schema": SCHEMA,
        "identity": IDENTITY,
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "independent_oos_evidence": False,
        "capital_risk_authority": False,
        "production_activation": False,
        "training": training,
        "held_out_window": {"start": str(HELD_OUT_START), "end": str(HELD_OUT_END), "dates": 49},
        "price_policy": {"minimum": str(MIN_PRICE), "maximum": str(MAX_PRICE), "minimum_edge": str(MIN_EDGE)},
        "network_policy": {
            "maximum_requests": price.NETWORK_LIMIT,
            "actual_requests": client.used,
            "maximum_requests_per_second": 4,
            "maximum_attempts_per_logical_get": 3,
            "retry_only_transport_or_http_5xx": True,
            "no_retry_http_429_or_other_4xx": True,
        },
        "historical_cutoffs": cutoffs,
        "fee_identities": fee_identities,
        "support_funnel": {
            "held_out_station_dates": sum(len(value) for value in rows_by_station.values()),
            "exact_q75_contracts": exact_contracts,
            "nonempty_candles": sum(
                row.get("reason") not in ("empty_candle", "no_exact_q75_greater_contract") for row in quote_rows
            ),
            "displayed_prices": sum(row.get("no_limit") is not None for row in quote_rows),
            "eligible_quotes": sum(row.get("candidate") is True for row in quote_rows),
        },
        "evaluation": evaluation,
        "quote_rows": quote_rows,
    }
    price.atomic_json(output_dir / "report.json", report)
    print(json.dumps({
        "frozen_score": training["frozen_score"],
        "development_support_passes": evaluation["development_support_passes"],
        "failed_development_gates": evaluation["failed_development_gates"],
        "support_funnel": report["support_funnel"],
        "selected_submissions": evaluation["selected_submissions"],
        "executable_public_trades": evaluation["executable_public_trades"],
        "realized_net_pnl": evaluation["realized_net_pnl"],
        "network_requests": client.used,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
