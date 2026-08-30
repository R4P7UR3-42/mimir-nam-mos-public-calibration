#!/usr/bin/env python3
"""Training-only low-temperature market calibration development."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.parse
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from market_implied import evaluate as market  # noqa: E402


IDENTITY = "daily_low_extreme_market_implied_no_18z_development_v1"
SCHEMA = "daily_low_extreme_market_implied_no_18z_development_v1"
DEVELOPMENT_SHA256 = "0e6f56df8189a3e234b7d5d16bb5b9390d968ec1b645f1481eb116632952c7cf"
TRAINING_SERIES_SHA256 = "65cff9a375c81967b2d6177401b11ae9527f85ff1de2db0f42f862ef179f0a21"
RESERVED_SERIES_SHA256 = "4a407d82e30e8a60aa2d3ff3d3cd587d464d8645156d9bcfbd8861404fe367b6"
START = dt.date(2025, 12, 13)
END = dt.date(2026, 3, 31)
MAX_PAGES_PER_SERIES = 10
MIN_ROWS = 100
MIN_DATES = 60
MIN_SERIES = 8
MIN_EDGE = Decimal("0.0150")
MAX_SERIES_SHARE = Decimal("0.20")
MAX_DATE_SHARE = Decimal("0.05")
PRIMARY_TAIL = 0.0125
HOLDOUT_TAIL = 0.10
CELL_DEFINITIONS = (
    ("upper", Decimal("0.7000"), Decimal("0.8000"), False, Decimal("0.7999"), "upper_0.70_0.80"),
    ("upper", Decimal("0.8000"), Decimal("0.9000"), False, Decimal("0.8999"), "upper_0.80_0.90"),
    ("upper", Decimal("0.9000"), Decimal("0.9500"), False, Decimal("0.9499"), "upper_0.90_0.95"),
    ("upper", Decimal("0.9500"), Decimal("0.9700"), True, Decimal("0.9700"), "upper_0.95_0.97"),
    ("lower", Decimal("0.7000"), Decimal("0.8000"), False, Decimal("0.7999"), "lower_0.70_0.80"),
    ("lower", Decimal("0.8000"), Decimal("0.9000"), False, Decimal("0.8999"), "lower_0.80_0.90"),
    ("lower", Decimal("0.9000"), Decimal("0.9500"), False, Decimal("0.9499"), "lower_0.90_0.95"),
    ("lower", Decimal("0.9500"), Decimal("0.9700"), True, Decimal("0.9700"), "lower_0.95_0.97"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    return parser.parse_args()


def load_inventory(path: Path, expected_hash: str, expected_count: int) -> list[str]:
    if market.file_sha256(path) != expected_hash:
        raise ValueError(f"Frozen inventory hash is invalid: {path.name}.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, list)
        or len(payload) != expected_count
        or payload != sorted(payload)
        or len(set(payload)) != expected_count
        or any(not isinstance(value, str) or not value.startswith("KXLOWT") for value in payload)
    ):
        raise ValueError(f"Frozen inventory is malformed: {path.name}.")
    return payload


class TrainingClient(market.PublicClient):
    def __init__(self, output_dir: Path, maximum: int, reserved_series: list[str]):
        super().__init__(output_dir, maximum)
        self.reserved_series = tuple(reserved_series)

    def fetch(self, url: str, label: str) -> dict[str, object]:
        decoded = urllib.parse.unquote(url)
        if any(ticker in decoded or ticker in label for ticker in self.reserved_series):
            raise ValueError("Reserved evaluation series access is forbidden during development.")
        return super().fetch(url, label)


def validate_historical_cutoff(client: TrainingClient) -> dict[str, object]:
    url = f"{market.BASE_URL}/historical/cutoff"
    payload = client.fetch(url, "historical-cutoff")
    market_cutoff = market.parse_timestamp(payload.get("market_settled_ts"), "historical market cutoff")
    last_boundary = dt.datetime.combine(END + dt.timedelta(days=1), dt.time(), tzinfo=dt.timezone.utc)
    if market_cutoff <= last_boundary:
        raise ValueError("Historical cutoff does not contain the complete training window.")
    return {
        "url": url,
        "market_settled_ts": market_cutoff.isoformat().replace("+00:00", "Z"),
    }


def exact_market_date_identity(row: dict[str, object], series_ticker: str) -> dt.date:
    ticker = row.get("ticker")
    event = row.get("event_ticker")
    if not isinstance(ticker, str) or not isinstance(event, str) or not ticker.startswith(f"{event}-"):
        raise ValueError(f"Historical market identity is malformed for {series_ticker}.")
    return market.event_market_date(event, series_ticker)


def market_date_for_row(row: dict[str, object], series_ticker: str) -> dt.date:
    ticker = str(row.get("ticker"))
    parsed = exact_market_date_identity(row, series_ticker)
    occurrence = row.get("occurrence_datetime")
    if (
        occurrence is not None
        and market.parse_timestamp(occurrence, f"{ticker} occurrence").date() != parsed + dt.timedelta(days=1)
    ):
        raise ValueError(f"Occurrence date conflicts for {ticker}.")
    return parsed


def validate_terminal_market(row: dict[str, object], series_ticker: str) -> dt.date | None:
    if row.get("result") == "scalar":
        settlement = row.get("settlement_value_dollars")
        try:
            settlement_value = Decimal(str(settlement))
        except Exception as error:
            raise ValueError(f"Exact scalar exclusion identity is invalid for {row.get('ticker')}.") from error
        if (
            row.get("status") == "finalized"
            and row.get("expiration_value") == ""
            and isinstance(settlement, str)
            and settlement_value.is_finite()
            and Decimal(0) <= settlement_value <= Decimal(1)
            and settlement_value.as_tuple().exponent == -4
        ):
            exact_market_date_identity(row, series_ticker)
            return None
        raise ValueError(f"Exact scalar exclusion identity is invalid for {row.get('ticker')}.")
    market_date = market_date_for_row(row, series_ticker)
    if (
        row.get("market_type") != "binary"
        or row.get("strike_type") not in ("greater", "less", "between")
        or row.get("result") not in ("yes", "no")
        or ("is_provisional" in row and row["is_provisional"] is not False)
        or ("mve_collection_ticker" in row and row["mve_collection_ticker"] not in (None, ""))
        or ("fee_waiver_expiration_time" in row and row["fee_waiver_expiration_time"] is not None)
    ):
        raise ValueError(f"Historical market is unsupported for {row.get('ticker')}.")
    return market_date


def discover_training_events(
    client: TrainingClient,
    series_ticker: str,
) -> dict[dt.date, list[dict[str, object]]]:
    events: dict[dt.date, list[dict[str, object]]] = defaultdict(list)
    excluded_scalar_dates: set[dt.date] = set()
    seen_tickers: set[str] = set()
    seen_cursors: set[str] = set()
    cursor = ""
    for page in range(MAX_PAGES_PER_SERIES):
        query = {"series_ticker": series_ticker, "limit": "1000"}
        if cursor:
            query["cursor"] = cursor
        url = f"{market.BASE_URL}/historical/markets?{urllib.parse.urlencode(query)}"
        payload = client.fetch(url, f"training-{series_ticker}-markets-page-{page + 1:02d}")
        rows = payload.get("markets")
        next_cursor = payload.get("cursor")
        if (
            not isinstance(rows, list)
            or any(not isinstance(row, dict) for row in rows)
            or not isinstance(next_cursor, str)
        ):
            raise ValueError(f"Historical market page is malformed for {series_ticker}.")
        for row in rows:
            ticker = str(row.get("ticker"))
            if ticker in seen_tickers:
                raise ValueError(f"Historical market is duplicated for {ticker}.")
            seen_tickers.add(ticker)
            market_date = validate_terminal_market(row, series_ticker)
            if market_date is None:
                excluded_scalar_dates.add(exact_market_date_identity(row, series_ticker))
                continue
            if START <= market_date <= END:
                events[market_date].append(row)
        if not next_cursor:
            break
        if next_cursor in seen_cursors or next_cursor == cursor:
            raise ValueError(f"Historical cursor repeated for {series_ticker}.")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    else:
        raise ValueError(f"Historical pagination exceeded {MAX_PAGES_PER_SERIES} pages for {series_ticker}.")
    for excluded_date in excluded_scalar_dates:
        events.pop(excluded_date, None)
    return dict(events)


def select_extremes(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    uppers = [
        row for row in rows
        if row.get("strike_type") == "greater" and row.get("floor_strike") is not None
        and row.get("cap_strike") is None
    ]
    lowers = [
        row for row in rows
        if row.get("strike_type") == "less" and row.get("floor_strike") is None
        and row.get("cap_strike") is not None
    ]
    if len(uppers) != 1 or len(lowers) != 1:
        raise ValueError("Daily low event does not contain one exact upper and lower extreme.")
    return {"upper": uppers[0], "lower": lowers[0]}


def decision_clock(market_date: dt.date) -> dt.datetime:
    return dt.datetime.combine(market_date - dt.timedelta(days=1), dt.time(18), tzinfo=dt.timezone.utc)


def cell_for(tail: str, price: Decimal) -> str | None:
    for expected_tail, low, high, inclusive_high, _maximum, label in CELL_DEFINITIONS:
        if tail == expected_tail and low <= price and (price <= high if inclusive_high else price < high):
            return label
    return None


def capture_quote(
    client: TrainingClient,
    series_ticker: str,
    market_date: dt.date,
    tail: str,
    row: dict[str, object],
) -> dict[str, object]:
    ticker = str(row["ticker"])
    clock = decision_clock(market_date)
    timestamp = int(clock.timestamp())
    url = (
        f"{market.BASE_URL}/historical/markets/{urllib.parse.quote(ticker, safe='')}/candlesticks?"
        + urllib.parse.urlencode({"start_ts": timestamp, "end_ts": timestamp, "period_interval": 60})
    )
    payload = client.fetch(url, f"training-{series_ticker}-{market_date.isoformat()}-{tail}-candle")
    candles = payload.get("candlesticks")
    if payload.get("ticker") != ticker or not isinstance(candles, list):
        raise ValueError(f"Candle response identity is invalid for {ticker}.")
    base = {
        "series_ticker": series_ticker,
        "event_ticker": row["event_ticker"],
        "market_ticker": ticker,
        "market_date": market_date.isoformat(),
        "tail": tail,
        "decision_at": clock.isoformat().replace("+00:00", "Z"),
        "outcome_no": int(row["result"] == "no"),
        "strike": str(row["floor_strike"] if tail == "upper" else row["cap_strike"]),
        "source_url": url,
    }
    if not candles:
        return {**base, "candidate": False, "reason": "empty_candle"}
    if len(candles) != 1 or not isinstance(candles[0], dict) or candles[0].get("end_period_ts") != timestamp:
        raise ValueError(f"Candle clock identity is invalid for {ticker}.")
    yes_bid = candles[0].get("yes_bid")
    if not isinstance(yes_bid, dict) or yes_bid.get("close") is None:
        return {**base, "candidate": False, "reason": "missing_yes_bid_close"}
    bid = market.decimal_value(yes_bid["close"], f"{ticker} YES bid")
    if bid <= 0 or bid >= 1:
        return {**base, "candidate": False, "reason": "boundary_yes_bid", "yes_bid": str(bid)}
    no_limit = Decimal(1) - bid
    cell = cell_for(tail, no_limit)
    if cell is None:
        return {
            **base,
            "candidate": False,
            "reason": "outside_frozen_cells",
            "yes_bid": str(bid),
            "no_limit": str(no_limit),
        }
    exact_fee = market.fee(no_limit)
    exact_return = Decimal(1) - no_limit - exact_fee if row["result"] == "no" else -no_limit - exact_fee
    return {
        **base,
        "candidate": True,
        "reason": "eligible_training_cell",
        "yes_bid": str(bid),
        "no_limit": str(no_limit),
        "fee": str(exact_fee),
        "exact_fee_return": str(exact_return),
        "cell": cell,
    }


def clustered_lower(rows: list[dict[str, object]], key: str, tail: float, seed: int) -> Decimal | None:
    return market.clustered_lower(rows, key, tail, seed)


def evaluate_cell(rows: list[dict[str, object]], index: int) -> dict[str, object]:
    tail, low, high, inclusive_high, maximum, label = CELL_DEFINITIONS[index]
    selected = [row for row in rows if row.get("candidate") is True and row.get("cell") == label]
    dates = {str(row["market_date"]) for row in selected}
    series = {str(row["series_ticker"]) for row in selected}
    series_counts = {value: sum(row["series_ticker"] == value for row in selected) for value in series}
    date_counts = {value: sum(row["market_date"] == value for row in selected) for value in dates}
    successes = sum(int(row["outcome_no"]) for row in selected)
    score = (Decimal(successes) + Decimal("0.5")) / (Decimal(len(selected)) + Decimal(1)) if selected else None
    return_lower = clustered_lower(selected, "exact_fee_return", PRIMARY_TAIL, 0x10A0C001 + index) if selected else None
    probability_lower = clustered_lower(selected, "outcome_no", PRIMARY_TAIL, 0x10A0C101 + index) if selected else None
    conservative_edge = probability_lower - maximum - market.fee(maximum) if probability_lower is not None else None
    holdouts = []
    for excluded in sorted(series):
        remaining = [row for row in selected if row["series_ticker"] != excluded]
        lower_return = clustered_lower(
            remaining, "exact_fee_return", HOLDOUT_TAIL, 0x10A0C201 + index,
        ) if remaining else None
        holdouts.append({
            "excluded_series_ticker": excluded,
            "lower_90_exact_fee_return": f"{lower_return:.8f}" if lower_return is not None else None,
            "passes": lower_return is not None and lower_return >= 0,
        })
    maximum_series_share = (
        Decimal(max(series_counts.values())) / Decimal(len(selected)) if selected else Decimal(1)
    )
    maximum_date_share = Decimal(max(date_counts.values())) / Decimal(len(selected)) if selected else Decimal(1)
    gates = {
        "minimum_100_rows": len(selected) >= MIN_ROWS,
        "minimum_60_dates": len(dates) >= MIN_DATES,
        "minimum_eight_series": len(series) >= MIN_SERIES,
        "series_concentration": maximum_series_share <= MAX_SERIES_SHARE,
        "date_concentration": maximum_date_share <= MAX_DATE_SHARE,
        "bonferroni_clustered_return_at_least_0015": return_lower is not None and return_lower >= MIN_EDGE,
        "leave_one_series_out_nonnegative": len(holdouts) >= MIN_SERIES and all(row["passes"] for row in holdouts),
        "bonferroni_probability_edge_at_least_0015": conservative_edge is not None and conservative_edge >= MIN_EDGE,
    }
    return {
        "menu_index": index + 1,
        "cell": label,
        "tail": tail,
        "minimum_price": str(low),
        "maximum_boundary": str(high),
        "maximum_inclusive": inclusive_high,
        "conservative_maximum_price": str(maximum),
        "conservative_maximum_fee": str(market.fee(maximum)),
        "rows": len(selected),
        "successes": successes,
        "independent_dates": len(dates),
        "series_count": len(series),
        "score_jeffreys": f"{score.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP):.8f}" if score is not None else None,
        "bonferroni_lower_exact_fee_return": f"{return_lower:.8f}" if return_lower is not None else None,
        "bonferroni_lower_outcome_probability": f"{probability_lower:.8f}" if probability_lower is not None else None,
        "minimum_conservative_edge": f"{conservative_edge:.8f}" if conservative_edge is not None else None,
        "maximum_series_share": f"{maximum_series_share:.8f}",
        "maximum_date_share": f"{maximum_date_share:.8f}",
        "series_holdouts": holdouts,
        "gates": gates,
        "admissible": all(gates.values()),
    }


def calibrate(rows: list[dict[str, object]]) -> dict[str, object]:
    cells = [evaluate_cell(rows, index) for index in range(len(CELL_DEFINITIONS))]
    admissible = [row for row in cells if row["admissible"]]
    selected = max(
        admissible,
        key=lambda row: (market.decimal_value(row["bonferroni_lower_exact_fee_return"], "cell lower return"), -int(row["menu_index"])),
    ) if admissible else None
    return {
        "multiple_test_cells": len(CELL_DEFINITIONS),
        "familywise_one_sided_alpha": "0.10",
        "bonferroni_tail": "0.0125",
        "cells": cells,
        "selected_cell": selected,
        "successor_freeze_permitted": selected is not None,
    }


def main() -> None:
    args = parse_args()
    market.assert_not_production_host()
    root = Path(__file__).resolve().parent
    if market.file_sha256(root / "DEVELOPMENT.md") != DEVELOPMENT_SHA256:
        raise ValueError("Development freeze hash is invalid.")
    training_series = load_inventory(root / "training_series.json", TRAINING_SERIES_SHA256, 12)
    reserved_series = load_inventory(root / "reserved_evaluation_series.json", RESERVED_SERIES_SHA256, 11)
    if set(training_series).intersection(reserved_series):
        raise ValueError("Training and reserved evaluation inventories overlap.")
    if args.max_requests != market.NETWORK_LIMIT:
        raise ValueError(f"The exact request ceiling is {market.NETWORK_LIMIT}.")
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    client = TrainingClient(output, args.max_requests, reserved_series)
    cutoff = validate_historical_cutoff(client)
    fee_identities = [market.validate_fee_identity(client, ticker, "training") for ticker in training_series]
    events = {ticker: discover_training_events(client, ticker) for ticker in training_series}
    rows: list[dict[str, object]] = []
    for market_date in market.date_range(START, END):
        for ticker in training_series:
            event_rows = events[ticker].get(market_date)
            if event_rows is None:
                continue
            extremes = select_extremes(event_rows)
            for tail in ("upper", "lower"):
                rows.append(capture_quote(client, ticker, market_date, tail, extremes[tail]))
            print(json.dumps({
                "series_ticker": ticker,
                "market_date": market_date.isoformat(),
                "network_requests": client.used,
            }, sort_keys=True), flush=True)
    calibration = calibrate(rows)
    report = {
        "schema": SCHEMA,
        "identity": IDENTITY,
        "research_only": True,
        "training_only": True,
        "evaluation_series_accessed": False,
        "production_database_accessed": False,
        "active_trading_capability_changed": False,
        "development_sha256": DEVELOPMENT_SHA256,
        "training_series_sha256": TRAINING_SERIES_SHA256,
        "reserved_evaluation_series_sha256": RESERVED_SERIES_SHA256,
        "training_start": START.isoformat(),
        "training_end": END.isoformat(),
        "historical_cutoff": cutoff,
        "network_policy": {
            "maximum_requests": market.NETWORK_LIMIT,
            "actual_requests": client.used,
            "maximum_requests_per_second": 4,
            "no_retry": True,
            "stop_on_http_429": True,
            "maximum_pages_per_series": MAX_PAGES_PER_SERIES,
        },
        "training_fee_identities": fee_identities,
        "captured_rows": len(rows),
        "candidate_rows": sum(row.get("candidate") is True for row in rows),
        "captured_dates": len({str(row["market_date"]) for row in rows}),
        "captured_series": len({str(row["series_ticker"]) for row in rows}),
        "calibration": calibration,
        "successor_freeze_permitted": calibration["successor_freeze_permitted"],
        "initial_evidence_passes": False,
        "scale_evidence_passes": False,
        "rows": rows,
    }
    market.atomic_json(output / "development.json", report)
    print(json.dumps({key: report[key] for key in (
        "schema", "captured_rows", "candidate_rows", "captured_dates", "captured_series",
        "successor_freeze_permitted",
    )}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
