#!/usr/bin/env python3
"""Evaluate frozen GFS MOS scores against historical executable Kalshi evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import urllib.parse
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import capture  # noqa: E402
from gfs_mos_price.profile import configure  # noqa: E402

configure(capture)
import evaluate as calibration  # noqa: E402
from nbm_q90_price import evaluate as market  # noqa: E402


SCHEMA = "gfs_mos_station_rolling_wilson90_executable_no_oos_evaluation_v1"
IDENTITY = "gfs_mos_station_rolling_wilson90_executable_no_oos_v1"
PARENT_RESULT_SHA256 = "2cdd2079394f6a3da426f90133fd0e69dc26e4015455f0edc355d78e835d0f62"
SOURCE_ADDENDUM_SHA256 = "e6d839ebc2ca7830e23d7d44935ea73e421ab4ae919a8eaac27c2b89a10bd1bf"
START = dt.date(2025, 12, 31)
END = dt.date(2026, 6, 28)
NETWORK_LIMIT = 12_000
MIN_PRICE = Decimal("0.55")
MAX_PRICE = Decimal("0.97")
MIN_EDGE = Decimal("0.0150")
BANDS = (
    (Decimal("0.90"), Decimal("0.93"), "0.90-0.93"),
    (Decimal("0.93"), Decimal("0.96"), "0.93-0.96"),
    (Decimal("0.96"), Decimal("1.0001"), "0.96-1.00"),
)
MONTH_NAMES = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    return parser.parse_args()


def decision_clock(market_date: dt.date) -> dt.datetime:
    return dt.datetime.combine(
        market_date - dt.timedelta(days=1),
        dt.time(20, 5),
        tzinfo=dt.timezone.utc,
    )


def exact_event_ticker(series_ticker: str, market_date: dt.date) -> str:
    return f"{series_ticker}-{market_date.year % 100:02d}{MONTH_NAMES[market_date.month]}{market_date.day:02d}"


def load_stations() -> list[dict[str, object]]:
    path = Path(__file__).with_name("stations.json")
    if capture.file_sha256(path) != capture.STATIONS_SHA256:
        raise ValueError("Frozen station/series inventory hash is invalid.")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(rows, list)
        or len(rows) != 10
        or any(
            not isinstance(row, dict)
            or set(row) != {"station_id", "series_ticker", "latitude", "longitude", "time_zone"}
            for row in rows
        )
        or len({row["station_id"] for row in rows}) != 10
        or len({row["series_ticker"] for row in rows}) != 10
    ):
        raise ValueError("Frozen station/series inventory is malformed.")
    return rows


def load_capture(path: Path, stations: list[dict[str, object]]) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    calibration_dates, evaluation_dates = capture.frozen_dates()
    expected_station_ids = {str(row["station_id"]) for row in stations}
    if (
        payload.get("schema") != capture.SCHEMA
        or payload.get("model_identity") != IDENTITY
        or payload.get("predeclaration_sha256") != capture.PREDECLARATION_SHA256
        or payload.get("stations_sha256") != capture.STATIONS_SHA256
        or payload.get("research_only") is not True
        or payload.get("active_trading_capability_changed") is not False
        or payload.get("production_database_accessed") is not False
        or payload.get("credential_required") is not False
        or payload.get("historical_price_data_inspected") is not False
        or payload.get("request_policy") != {
            "no_retry": True,
            "stop_on_http_429": True,
            "maximum_requests": 13,
            "actual_network_requests": 13,
        }
        or payload.get("design") != {
            "forecast_model": "noaa_gfs_station_mos_n_x",
            "source_model": "GFS",
            "forecast_runtime_utc": "12:00:00",
            "forecast_available_by_utc": "20:00:00",
            "duplicate_policy": "collapse_only_identical_semantic_selected_row",
            "selected_exact_duplicates_per_station": None,
            "global_optional_schema_required": False,
            "isd_history_through_window_required": False,
            "minimum_isd_history_end": "20250825",
            "calibration_first_date": "2025-09-01",
            "calibration_last_date": "2025-12-30",
            "calibration_dates": 121,
            "evaluation_first_date": "2025-12-31",
            "evaluation_last_date": "2026-06-28",
            "evaluation_dates": 180,
            "station_count": 10,
        }
        or payload.get("coverage") != {
            "requested_dates": 301,
            "complete_dates": 301,
            "station_dates": 3010,
            "selected_exact_duplicate_rows": 0,
        }
    ):
        raise ValueError("GFS economic source capture identity is invalid.")
    rows = payload.get("rows")
    sources = payload.get("forecast_sources")
    if (
        not isinstance(rows, list)
        or len(rows) != 3010
        or any(not isinstance(row, dict) for row in rows)
        or not isinstance(sources, list)
        or len(sources) != 10
        or {source.get("station_id") for source in sources if isinstance(source, dict)} != expected_station_ids
        or any(
            not isinstance(source, dict)
            or source.get("selected_exact_duplicate_count") != 0
            or not capture.REQUIRED_MOS_FIELDS.issubset(source.get("csv_fields", []))
            for source in sources
        )
    ):
        raise ValueError("GFS economic source coverage is invalid.")
    expected = {
        (station, date)
        for station in expected_station_ids
        for date in calibration_dates + evaluation_dates
    }
    actual = {(row.get("station_id"), row.get("market_date")) for row in rows}
    if actual != expected:
        raise ValueError("GFS economic station/date identity is incomplete or duplicated.")
    for row in rows:
        calibration.validate_capture_row(row)
        forecast = market.decimal_value(row.get("forecast_high_f"), "forecast high")
        observed = market.decimal_value(row.get("observed_high_f"), "observed high")
        if forecast != forecast.to_integral_value() or observed != observed.to_integral_value():
            raise ValueError("GFS economic contract mapping requires whole-degree forecast and outcome values.")
    return payload


def historical_cutoffs(client: market.PublicClient) -> dict[str, str]:
    cutoffs = market.historical_cutoffs(client)
    if market.parse_timestamp(cutoffs["market_settled_ts"], "market cutoff") <= dt.datetime.combine(
        END + dt.timedelta(days=2), dt.time(), tzinfo=dt.timezone.utc
    ):
        raise ValueError("Historical market cutoff does not cover the frozen window.")
    if market.parse_timestamp(cutoffs["trades_created_ts"], "trade cutoff") <= decision_clock(END) + dt.timedelta(minutes=5):
        raise ValueError("Historical trade cutoff does not cover the frozen window.")
    return cutoffs


def event_markets(
    client: market.PublicClient,
    series_ticker: str,
    market_date: dt.date,
) -> list[dict[str, object]]:
    event = exact_event_ticker(series_ticker, market_date)
    merged: dict[str, tuple[str, dict[str, object]]] = {}
    for partition, path in (("live", "markets"), ("historical", "historical/markets")):
        query = {"event_ticker": event, "limit": "1000"}
        if partition == "live":
            query["mve_filter"] = "exclude"
        url = f"{market.BASE_URL}/{path}?{urllib.parse.urlencode(query)}"
        payload = client.fetch(url, f"{series_ticker}-{market_date.isoformat()}-{partition}-markets")
        values = payload.get("markets")
        if (
            not isinstance(values, list)
            or any(not isinstance(value, dict) for value in values)
            or payload.get("cursor") not in (None, "")
        ):
            raise ValueError(f"Exact event inventory is nonterminal for {event}|{partition}.")
        for value in values:
            ticker = value.get("ticker")
            if (
                not isinstance(ticker, str)
                or not ticker.startswith(f"{event}-")
                or value.get("event_ticker") != event
                or market.event_market_date(value.get("event_ticker"), series_ticker) != market_date
            ):
                raise ValueError(f"Exact event identity drifted for {event}|{partition}.")
            prior = merged.get(ticker)
            if prior is not None and market.market_partition_identity(prior[1]) != market.market_partition_identity(value):
                raise ValueError(f"Market identity conflicts across partitions for {ticker}.")
            if prior is None or partition == "historical":
                merged[ticker] = (partition, value)
    return [{**value, "_source_partition": partition} for partition, value in merged.values()]


def rolling_history(
    rows: list[dict[str, object]],
    market_date: dt.date,
) -> list[dict[str, object]]:
    cutoff = market_date - dt.timedelta(days=2)
    eligible = [row for row in rows if dt.date.fromisoformat(str(row["market_date"])) <= cutoff]
    history = eligible[-120:]
    dates = [dt.date.fromisoformat(str(row["market_date"])) for row in history]
    if (
        len(history) != 120
        or dates[-1] != cutoff
        or any(right - left != dt.timedelta(days=1) for left, right in zip(dates, dates[1:]))
    ):
        raise ValueError(f"Rolling GFS history is incomplete for {market_date}.")
    return history


def score_market(
    source_row: dict[str, object],
    history: list[dict[str, object]],
    source_market: dict[str, object],
) -> dict[str, object] | None:
    floor = market.decimal_value(source_market.get("floor_strike"), "floor strike")
    forecast = market.decimal_value(source_row["forecast_high_f"], "forecast high")
    observed = market.decimal_value(source_row["observed_high_f"], "observed high")
    losing_boundary = floor + Decimal("0.5")
    distance = losing_boundary - forecast
    if not Decimal("4.0") <= distance < Decimal("8.0"):
        return None
    ticker = source_market.get("ticker")
    outcome_no = observed <= floor
    if (
        not isinstance(ticker, str)
        or floor != floor.to_integral_value()
        or source_market.get("market_type") != "binary"
        or source_market.get("strike_type") != "greater"
        or source_market.get("cap_strike") is not None
        or source_market.get("yes_sub_title") != f"{int(floor) + 1}° or above"
        or source_market.get("result") not in ("yes", "no")
        or (source_market.get("result") == "no") != outcome_no
        or ("is_provisional" in source_market and source_market["is_provisional"] is not False)
        or ("mve_collection_ticker" in source_market and source_market["mve_collection_ticker"] not in (None, ""))
        or ("fee_waiver_expiration_time" in source_market and source_market["fee_waiver_expiration_time"] is not None)
    ):
        raise ValueError(f"Exact GFS greater-contract identity is invalid for {ticker}.")
    successes = sum(
        market.decimal_value(row["residual_f"], "history residual") <= distance
        for row in history
    )
    score = calibration.wilson_lower(successes, 120)
    if score < Decimal("0.9000"):
        return None
    return {
        "station_id": source_row["station_id"],
        "market_date": source_row["market_date"],
        "forecast_high_f": str(forecast),
        "observed_high_f": str(observed),
        "event_ticker": source_market["event_ticker"],
        "market_ticker": ticker,
        "floor_strike": str(floor),
        "losing_boundary_f": str(losing_boundary),
        "distance_f": str(distance),
        "history_first_date": history[0]["market_date"],
        "history_last_date": history[-1]["market_date"],
        "history_count": 120,
        "history_successes": successes,
        "score": str(score),
        "outcome_no": int(outcome_no),
        "_source_partition": source_market["_source_partition"],
    }


def capture_quote(
    client: market.PublicClient,
    series_ticker: str,
    candidate: dict[str, object],
) -> dict[str, object]:
    ticker = str(candidate["market_ticker"])
    partition = candidate["_source_partition"]
    if partition == "historical":
        path = f"historical/markets/{urllib.parse.quote(ticker, safe='')}/candlesticks"
    elif partition == "live":
        path = f"series/{urllib.parse.quote(series_ticker, safe='')}/markets/{urllib.parse.quote(ticker, safe='')}/candlesticks"
    else:
        raise ValueError(f"Candle partition is invalid for {ticker}.")
    clock = decision_clock(dt.date.fromisoformat(str(candidate["market_date"])))
    timestamp = int(clock.timestamp())
    url = f"{market.BASE_URL}/{path}?" + urllib.parse.urlencode(
        {"start_ts": timestamp, "end_ts": timestamp, "period_interval": 1}
    )
    payload = client.fetch(url, f"{ticker}-decision-candle")
    candles = payload.get("candlesticks")
    base = {key: value for key, value in candidate.items() if key != "_source_partition"}
    base.update({"decision_at": clock.isoformat().replace("+00:00", "Z"), "quote_source_url": url})
    if payload.get("ticker") != ticker or not isinstance(candles, list):
        raise ValueError(f"Candle response identity is invalid for {ticker}.")
    if not candles:
        return {**base, "candidate": False, "reason": "empty_candle"}
    if len(candles) != 1 or not isinstance(candles[0], dict) or candles[0].get("end_period_ts") != timestamp:
        raise ValueError(f"Candle clock identity is invalid for {ticker}.")
    yes_bid = candles[0].get("yes_bid")
    if not isinstance(yes_bid, dict) or yes_bid.get("close") is None:
        return {**base, "candidate": False, "reason": "missing_yes_bid_close"}
    bid = market.decimal_value(yes_bid["close"], "YES bid")
    if bid <= 0 or bid >= 1:
        return {**base, "candidate": False, "reason": "boundary_yes_bid", "yes_bid": str(bid)}
    no_limit = Decimal(1) - bid
    if no_limit * 100 != (no_limit * 100).to_integral_value():
        raise ValueError(f"NO limit is not exact-cent for {ticker}.")
    exact_fee = market.fee(no_limit)
    edge = market.decimal_value(candidate["score"], "score") - no_limit - exact_fee
    eligible = MIN_PRICE <= no_limit <= MAX_PRICE and edge >= MIN_EDGE
    return {
        **base,
        "candidate": eligible,
        "reason": "eligible_quote" if eligible else "price_or_edge_outside_policy",
        "yes_bid": str(bid),
        "no_limit": str(no_limit),
        "fee": str(exact_fee),
        "conservative_edge": f"{edge:.8f}",
    }


def maximum_drawdown(returns: list[Decimal]) -> Decimal:
    return market.maximum_drawdown(returns)


def evaluate_rows(
    client: market.PublicClient,
    quote_rows: list[dict[str, object]],
    trade_cutoff: str,
) -> dict[str, object]:
    by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in quote_rows:
        if row.get("candidate") is True:
            by_date[str(row["market_date"])].append(row)
    selections = []
    for market_date in capture.date_range(START, END):
        rows = by_date.get(market_date, [])
        if not rows:
            continue
        rows.sort(key=lambda row: (
            -market.decimal_value(row["conservative_edge"], "edge"),
            market.decimal_value(row["no_limit"], "NO limit"),
            -market.decimal_value(row["score"], "score"),
            str(row["market_ticker"]),
        ))
        selections.append(rows[0])
    for selection in selections:
        fill = market.fetch_executable_trade(client, selection, trade_cutoff)
        selection["executable_trade"] = fill
        if fill is None:
            selection["submission_return"] = "0"
            continue
        price = market.decimal_value(fill["no_price"], "fill price")
        fee = market.decimal_value(fill["fee"], "fill fee")
        selection["submission_return"] = str(
            Decimal(1) - price - fee if selection["outcome_no"] == 1 else -price - fee
        )
    selected_dates = {str(row["market_date"]) for row in selections}
    selected_stations = {str(row["station_id"]) for row in selections}
    station_counts: dict[str, int] = defaultdict(int)
    for row in selections:
        station_counts[str(row["station_id"])] += 1
    outcomes = [Decimal(row["outcome_no"]) for row in selections]
    scores = [market.decimal_value(row["score"], "score") for row in selections]
    prices = [market.decimal_value(row["no_limit"], "NO limit") for row in selections]
    model_brier = sum(((score - outcome) ** 2 for score, outcome in zip(scores, outcomes)), Decimal(0)) / Decimal(len(selections)) if selections else None
    price_brier = sum(((price - outcome) ** 2 for price, outcome in zip(prices, outcomes)), Decimal(0)) / Decimal(len(selections)) if selections else None
    brier_skill = Decimal(1) - model_brier / price_brier if model_brier is not None and price_brier is not None and price_brier > 0 else None
    band_results = []
    for low, high, label in BANDS:
        rows = [row for row in selections if low <= market.decimal_value(row["score"], "score") < high]
        dates = {str(row["market_date"]) for row in rows}
        observed = sum((Decimal(row["outcome_no"]) for row in rows), Decimal(0)) / Decimal(len(rows)) if rows else None
        mean_score = sum((market.decimal_value(row["score"], "score") for row in rows), Decimal(0)) / Decimal(len(rows)) if rows else None
        error = abs(observed - mean_score) if observed is not None and mean_score is not None else None
        band_results.append({
            "band": label,
            "rows": len(rows),
            "independent_dates": len(dates),
            "observed": f"{observed:.8f}" if observed is not None else None,
            "mean_score": f"{mean_score:.8f}" if mean_score is not None else None,
            "absolute_error": f"{error:.8f}" if error is not None else None,
            "represented": bool(rows),
            "passes": not rows or (len(dates) >= 30 and error is not None and error <= Decimal("0.05")),
        })
    lower90 = market.clustered_lower(selections, "submission_return", 0.10, 0x6F534D31) if selections else None
    holdouts = []
    for station in sorted(selected_stations):
        rows = [row for row in selections if row["station_id"] != station]
        lower = market.clustered_lower(rows, "submission_return", 0.10, 0x6F534D31) if rows else None
        holdouts.append({
            "excluded_station_id": station,
            "lower_90_submission_return": f"{lower:.8f}" if lower is not None else None,
            "passes": lower is not None and lower >= 0,
        })
    returns = [market.decimal_value(row["submission_return"], "submission return") for row in selections]
    fills = [row for row in selections if row.get("executable_trade") is not None]
    realized = sum(returns, Decimal(0))
    drawdown = maximum_drawdown(returns)
    maximum_station_share = Decimal(max(station_counts.values(), default=0)) / Decimal(len(selections)) if selections else Decimal(1)
    maximum_date_share = Decimal(1) / Decimal(len(selections)) if selections else Decimal(1)
    projection = math.ceil(100 / float(lower90)) if lower90 is not None and lower90 > 0 else None
    maximum_all_in = max((
        market.decimal_value(row["executable_trade"]["no_price"], "fill price")
        + market.decimal_value(row["executable_trade"]["fee"], "fill fee")
        for row in fills
    ), default=None)
    gates = {
        "one_hundred_selected_dates": len(selections) >= 100 and len(selected_dates) == len(selections),
        "at_least_eight_stations": len(selected_stations) >= 8,
        "positive_brier_skill": brier_skill is not None and brier_skill > 0,
        "represented_reliability_bands": any(row["represented"] for row in band_results) and all(row["passes"] for row in band_results),
        "thirty_executable_fills": len(fills) >= 30 and len({str(row["market_date"]) for row in fills}) >= 30,
        "positive_realized_net_pnl": realized > 0,
        "drawdown_at_most_five": drawdown <= Decimal("5"),
        "clustered_90_submission_return_positive": lower90 is not None and lower90 > 0,
        "leave_one_station_out": len(holdouts) >= 8 and all(row["passes"] for row in holdouts),
        "station_concentration": maximum_station_share <= Decimal("0.15"),
        "date_concentration": maximum_date_share <= Decimal("0.01"),
        "scale_250_date_clustered_95": False,
    }
    initial_names = [name for name in gates if name != "scale_250_date_clustered_95"]
    return {
        "selected_submissions": len(selections),
        "selected_independent_dates": len(selected_dates),
        "selected_station_count": len(selected_stations),
        "model_brier": f"{model_brier:.8f}" if model_brier is not None else None,
        "displayed_price_brier": f"{price_brier:.8f}" if price_brier is not None else None,
        "brier_skill": f"{brier_skill:.8f}" if brier_skill is not None else None,
        "reliability_bands": band_results,
        "executable_public_trades": len(fills),
        "executable_trade_dates": len({str(row["market_date"]) for row in fills}),
        "realized_net_pnl": f"{realized:.4f}",
        "maximum_drawdown": f"{drawdown:.4f}",
        "lower_90_submission_return": f"{lower90:.8f}" if lower90 is not None else None,
        "maximum_station_share": f"{maximum_station_share:.8f}",
        "maximum_date_share": f"{maximum_date_share:.8f}",
        "station_holdouts": holdouts,
        "projected_contracts_to_100": projection,
        "projected_gross_turnover": f"{Decimal(projection) * maximum_all_in:.4f}" if projection is not None and maximum_all_in is not None else None,
        "projection_is_guaranteed": False,
        "capital_risk_authority": False,
        "production_activation": False,
        "gates": gates,
        "initial_economic_evidence_passes": all(gates[name] for name in initial_names),
        "failed_initial_gates": [name for name in initial_names if not gates[name]],
        "selections": selections,
    }


def main() -> None:
    args = parse_args()
    market.assert_not_production_host()
    root = Path(__file__).resolve().parent
    if capture.file_sha256(root / "PREDECLARATION.md") != capture.PREDECLARATION_SHA256:
        raise ValueError("Frozen economic predeclaration hash is invalid.")
    if capture.file_sha256(root / "SOURCE_CONTRACT_ADDENDUM.md") != SOURCE_ADDENDUM_SHA256:
        raise ValueError("Frozen source-contract addendum hash is invalid.")
    if capture.file_sha256(root.parent / "gfs_mos" / "RESULT.md") != PARENT_RESULT_SHA256:
        raise ValueError("Passing parent result hash is invalid.")
    stations = load_stations()
    source_path = Path(args.capture).resolve()
    source = load_capture(source_path, stations)
    if args.max_requests != NETWORK_LIMIT:
        raise ValueError(f"The frozen Kalshi request ceiling is exactly {NETWORK_LIMIT}.")
    market.NETWORK_LIMIT = NETWORK_LIMIT
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    client = market.PublicClient(output_dir, args.max_requests)
    fee_identities = [market.validate_fee_identity(client, str(row["series_ticker"])) for row in stations]
    cutoffs = historical_cutoffs(client)
    rows_by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in source["rows"]:
        rows_by_station[str(row["station_id"])].append(row)
    for rows in rows_by_station.values():
        rows.sort(key=lambda row: str(row["market_date"]))
    quote_rows = []
    funnel = {
        "source_station_dates": 1800,
        "event_inventories": 0,
        "score_eligible_contracts": 0,
        "nonempty_candles": 0,
        "eligible_quotes": 0,
    }
    evaluation_dates = capture.date_range(START, END)
    for station in stations:
        station_id = str(station["station_id"])
        series_ticker = str(station["series_ticker"])
        by_date = {str(row["market_date"]): row for row in rows_by_station[station_id]}
        for market_date_text in evaluation_dates:
            market_date = dt.date.fromisoformat(market_date_text)
            source_row = by_date[market_date_text]
            history = rolling_history(rows_by_station[station_id], market_date)
            markets = event_markets(client, series_ticker, market_date)
            funnel["event_inventories"] += 1
            seen_floor: set[Decimal] = set()
            for source_market in markets:
                if source_market.get("strike_type") != "greater":
                    continue
                floor = market.decimal_value(source_market.get("floor_strike"), "floor strike")
                candidate = score_market(source_row, history, source_market)
                if candidate is None:
                    continue
                if floor in seen_floor:
                    raise ValueError(f"Eligible floor is duplicated for {series_ticker}|{market_date_text}|{floor}.")
                seen_floor.add(floor)
                funnel["score_eligible_contracts"] += 1
                quoted = capture_quote(client, series_ticker, candidate)
                if quoted["reason"] != "empty_candle":
                    funnel["nonempty_candles"] += 1
                if quoted["candidate"] is True:
                    funnel["eligible_quotes"] += 1
                quote_rows.append(quoted)
            print(json.dumps({
                "station_id": station_id,
                "market_date": market_date_text,
                "score_eligible_contracts": len(seen_floor),
                "network_requests": client.used,
            }, sort_keys=True), flush=True)
    result = evaluate_rows(client, quote_rows, cutoffs["trades_created_ts"])
    report = {
        "schema": SCHEMA,
        "identity": IDENTITY,
        "predeclaration_sha256": capture.PREDECLARATION_SHA256,
        "stations_sha256": capture.STATIONS_SHA256,
        "parent_result_sha256": PARENT_RESULT_SHA256,
        "source_contract_addendum_sha256": SOURCE_ADDENDUM_SHA256,
        "source_capture_sha256": capture.file_sha256(source_path),
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "historical_price_data_inspected": True,
        "network_policy": {
            "maximum_requests": NETWORK_LIMIT,
            "actual_requests": client.used,
            "maximum_requests_per_second": 4,
            "no_retry": True,
            "stop_on_http_429": True,
        },
        "historical_cutoffs": cutoffs,
        "fee_identities": fee_identities,
        "support_funnel": funnel,
        "evaluation": result,
        "quote_rows": quote_rows,
    }
    market.atomic_json(output_dir / "report.json", report)
    print(json.dumps({
        "initial_economic_evidence_passes": result["initial_economic_evidence_passes"],
        "failed_initial_gates": result["failed_initial_gates"],
        "support_funnel": funnel,
        "selected_submissions": result["selected_submissions"],
        "executable_public_trades": result["executable_public_trades"],
        "realized_net_pnl": result["realized_net_pnl"],
        "network_requests": client.used,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
