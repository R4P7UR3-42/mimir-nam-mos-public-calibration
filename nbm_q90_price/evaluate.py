#!/usr/bin/env python3
"""One-shot NBM Q90 exact-threshold historical price/fill development audit."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING, getcontext
from pathlib import Path


getcontext().prec = 40
SCHEMA = "noaa_nbm_v5_q90_exact_threshold_no_development_evaluation_v2"
IDENTITY = "noaa_nbm_v5_q90_exact_threshold_no_development_v2"
CAPTURE_SCHEMA = "noaa_nbm_v5_qmd_max_t_capture_v1"
MODEL = "noaa_nbm_v5_qmd_station_max_t_percentiles_v1"
PREDECLARATION_SHA256 = "9f9081b5a986183955e7d8335ce8e31b94cbfcc3c496ae8476bc0cc5209f192b"
STATION_SERIES_SHA256 = "98a46e35e06c485cfcaa2b2632a2559b90cb5012491f718f5a570d13a26cdbbd"
INPUT_SHA256 = {
    "33155927949.json": "658b4c8d9a0c4361bb2e91efb1d44eda2d82f37112fcc4f176078811e3501430",
    "33156510785.json": "a759de0e02a095ee38d26b452aa4a922ec09162d1e90552d1b9fafd7147d7f45",
    "33156512445.json": "dceddb96a28c1899f1f6051bc074749b675bb1cf9c4900488994acb2a4d617cd",
    "33156598208.json": "1d5110c2b94be884c70e254866415176109e3b6a26c95592b42cb8df45f22992",
}
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
PARENT_START = dt.date(2026, 5, 7)
DEVELOPMENT_START = dt.date(2026, 5, 8)
DEVELOPMENT_END = dt.date(2026, 8, 14)
EXPECTED_PARENT_DATES = 100
EXPECTED_DEVELOPMENT_DATES = 99
LIVE_CLOSE_START = 1_778_198_400  # 2026-05-08T00:00:00Z
LIVE_CLOSE_END_EXCLUSIVE = 1_786_838_400  # 2026-08-16T00:00:00Z
NETWORK_LIMIT = 3_000
BOOTSTRAP_SAMPLES = 10_000
PROBABILITY = Decimal("0.933000")
FEE_RATE = Decimal("0.07")
FEE_QUANTUM = Decimal("0.0001")
MIN_PRICE = Decimal("0.55")
MAX_PRICE = Decimal("0.97")
MIN_EDGE = Decimal("0.0150")
MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    return parser.parse_args()


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes())


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def create_once(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"Create-once source changed: {path.name}.")
        return
    path.write_bytes(payload)


def date_range(start: dt.date, end: dt.date) -> list[dt.date]:
    output = []
    current = start
    while current <= end:
        output.append(current)
        current += dt.timedelta(days=1)
    return output


def parse_timestamp(value: object, label: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label} is not an exact UTC timestamp.")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} is malformed.") from error
    if parsed.tzinfo != dt.timezone.utc:
        raise ValueError(f"{label} is not UTC.")
    return parsed


def decimal_value(value: object, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as error:
        raise ValueError(f"{label} is malformed.") from error
    if not parsed.is_finite():
        raise ValueError(f"{label} is non-finite.")
    return parsed


def fee(price: Decimal) -> Decimal:
    if price < 0 or price > 1:
        raise ValueError("Fee price is outside [0,1].")
    return (FEE_RATE * price * (Decimal(1) - price)).quantize(FEE_QUANTUM, rounding=ROUND_CEILING)


def quote_is_eligible(no_limit: Decimal, edge: Decimal) -> bool:
    """Keep the frozen economic boundaries independently regression-testable."""
    return MIN_PRICE <= no_limit <= MAX_PRICE and edge >= MIN_EDGE


def decision_clock(market_date: dt.date) -> dt.datetime:
    return dt.datetime.combine(market_date - dt.timedelta(days=1), dt.time(14, 30), tzinfo=dt.timezone.utc)


def event_market_date(event_ticker: object, series_ticker: str) -> dt.date:
    if not isinstance(event_ticker, str) or not event_ticker.startswith(f"{series_ticker}-"):
        raise ValueError(f"Event identity is invalid for {series_ticker}.")
    suffix = event_ticker.removeprefix(f"{series_ticker}-")
    if len(suffix) not in (6, 7) or not suffix[:2].isdigit() or suffix[2:5] not in MONTHS or not suffix[5:].isdigit():
        raise ValueError(f"Event date identity is invalid for {event_ticker}.")
    try:
        return dt.date(2000 + int(suffix[:2]), MONTHS[suffix[2:5]], int(suffix[5:]))
    except ValueError as error:
        raise ValueError(f"Event date is malformed for {event_ticker}.") from error


def event_market_date_suffix(event_ticker: object) -> dt.date:
    """Parse a provider-returned event date before applying the in-window identity gate."""
    if not isinstance(event_ticker, str):
        raise ValueError("Historical event date identity is missing.")
    match = re.search(r"(?:^|-)(\d{2})([A-Z]{3})(\d{1,2})$", event_ticker)
    if match is None or match.group(2) not in MONTHS:
        raise ValueError(f"Historical event date identity is invalid for {event_ticker}.")
    try:
        return dt.date(2000 + int(match.group(1)), MONTHS[match.group(2)], int(match.group(3)))
    except ValueError as error:
        raise ValueError(f"Historical event date is malformed for {event_ticker}.") from error


def assert_not_production_host() -> None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/api/status", timeout=1) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError):
        return
    if not isinstance(payload, dict) or payload.get("environment") == "production":
        raise ValueError("NBM Q90 price acquisition is forbidden on a production Mimir host.")


class PublicClient:
    def __init__(self, output_dir: Path, maximum: int):
        if maximum != NETWORK_LIMIT:
            raise ValueError(f"The frozen request ceiling is exactly {NETWORK_LIMIT}.")
        self.output_dir = output_dir
        self.maximum = maximum
        self.used = 0
        self.last_started = 0.0

    def fetch(self, url: str, label: str) -> dict[str, object]:
        if self.used >= self.maximum:
            raise ValueError("Frozen network request ceiling exhausted.")
        delay = Decimal("0.25") - Decimal(str(time.monotonic() - self.last_started))
        if delay > 0:
            time.sleep(float(delay))
        self.last_started = time.monotonic()
        self.used += 1
        request = urllib.request.Request(url, headers={"User-Agent": "mimir-nbm-q90-public-development/1"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                headers = {key.lower(): value for key, value in response.headers.items()}
                status = response.getcode()
        except urllib.error.HTTPError as error:
            error_body = error.read()
            error_headers = {key.lower(): value for key, value in error.headers.items()}
            create_once(self.output_dir / "raw" / f"{label}.error-body", error_body)
            atomic_json(self.output_dir / "raw" / f"{label}.error.json", {
                "request_index": self.used,
                "request_url": url,
                "response_status": error.code,
                "response_sha256": sha256(error_body),
                "response_headers": error_headers,
            })
            if error.code == 429:
                raise ValueError("Provider acquisition stopped on HTTP 429 without retry.") from error
            raise
        create_once(self.output_dir / "raw" / f"{label}.json", body)
        atomic_json(self.output_dir / "raw" / f"{label}.headers.json", headers)
        atomic_json(self.output_dir / "raw" / f"{label}.request.json", {
            "request_index": self.used,
            "request_url": url,
            "response_status": status,
            "response_sha256": sha256(body),
        })
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise ValueError(f"Provider JSON is malformed for {label}.") from error
        if not isinstance(payload, dict):
            raise ValueError(f"Provider payload is not an object for {label}.")
        return payload


def validate_fee_identity(client: PublicClient, series_ticker: str) -> dict[str, object]:
    encoded = urllib.parse.quote(series_ticker, safe="")
    series_url = f"{BASE_URL}/series/{encoded}"
    series_payload = client.fetch(series_url, f"{series_ticker}-series")
    series = series_payload.get("series")
    if (
        not isinstance(series, dict)
        or series.get("ticker") != series_ticker
        or series.get("category") != "Climate and Weather"
        or series.get("fee_type") != "quadratic"
        or series.get("fee_multiplier") != 1
    ):
        raise ValueError(f"Fee baseline identity is invalid for {series_ticker}.")
    changes_url = f"{BASE_URL}/series/fee_changes?" + urllib.parse.urlencode(
        {"series_ticker": series_ticker, "show_historical": "true"}
    )
    changes_payload = client.fetch(changes_url, f"{series_ticker}-fee-changes")
    if changes_payload != {"series_fee_change_arr": []}:
        raise ValueError(f"Fee history is not the unchanged baseline for {series_ticker}.")
    return {
        "series_ticker": series_ticker,
        "fee_type": "quadratic",
        "provider_fee_multiplier": "1",
        "base_coefficient": "0.07",
        "balance_precision": "0.0001",
        "series_url": series_url,
        "changes_url": changes_url,
    }


def market_pages(
    client: PublicClient, series_ticker: str, partition: str
) -> list[dict[str, object]]:
    if partition not in ("live", "historical"):
        raise ValueError("Market partition is invalid.")
    markets: list[dict[str, object]] = []
    cursor = ""
    seen_cursors: set[str] = set()
    for page in range(1, 11):
        if partition == "live":
            path = "markets"
            query = {
                "series_ticker": series_ticker,
                "min_close_ts": str(LIVE_CLOSE_START),
                "max_close_ts": str(LIVE_CLOSE_END_EXCLUSIVE),
                "limit": "1000",
                "mve_filter": "exclude",
            }
        else:
            path = "historical/markets"
            query = {"limit": "1000", "series_ticker": series_ticker}
        if cursor:
            query["cursor"] = cursor
        url = f"{BASE_URL}/{path}?{urllib.parse.urlencode(query)}"
        payload = client.fetch(url, f"{series_ticker}-{partition}-markets-{page}")
        page_markets = payload.get("markets")
        next_cursor = payload.get("cursor")
        if not isinstance(page_markets, list) or any(not isinstance(row, dict) for row in page_markets):
            raise ValueError(f"{partition} market page is malformed for {series_ticker}.")
        if not isinstance(next_cursor, str):
            raise ValueError(f"{partition} market cursor is malformed for {series_ticker}.")
        markets.extend(page_markets)
        cursor = next_cursor
        if not cursor:
            break
        if cursor in seen_cursors:
            raise ValueError(f"{partition} market pagination repeated a cursor for {series_ticker}.")
        seen_cursors.add(cursor)
    if cursor:
        raise ValueError(f"{partition} market pagination exceeded ten pages for {series_ticker}.")
    return markets


def market_partition_identity(market: dict[str, object]) -> dict[str, object]:
    return {
        "event_ticker": market.get("event_ticker"),
        "market_type": market.get("market_type"),
        "strike_type": market.get("strike_type"),
        "floor_strike": (
            str(decimal_value(market["floor_strike"], "floor strike"))
            if market.get("floor_strike") is not None else None
        ),
        "cap_strike": (
            str(decimal_value(market["cap_strike"], "cap strike"))
            if market.get("cap_strike") is not None else None
        ),
        "result": market.get("result"),
        "yes_sub_title": market.get("yes_sub_title"),
        "status": market.get("status"),
        "is_provisional": market.get("is_provisional"),
        "mve_collection_ticker": market.get("mve_collection_ticker"),
        "fee_waiver_expiration_time": market.get("fee_waiver_expiration_time"),
    }


def discover_markets(client: PublicClient, series_ticker: str) -> dict[dt.date, list[dict[str, object]]]:
    merged: dict[str, tuple[str, dict[str, object]]] = {}
    for partition in ("live", "historical"):
        seen_partition_tickers: set[str] = set()
        for market in market_pages(client, series_ticker, partition):
            market_date = event_market_date_suffix(market.get("event_ticker"))
            if market_date < DEVELOPMENT_START or market_date > DEVELOPMENT_END:
                continue
            ticker = market.get("ticker")
            if (
                not isinstance(ticker, str)
                or not ticker.startswith(f"{series_ticker}-")
                or not isinstance(market.get("event_ticker"), str)
                or not str(market["event_ticker"]).startswith(f"{series_ticker}-")
                or event_market_date(market["event_ticker"], series_ticker) != market_date
            ):
                raise ValueError(f"In-window {partition} market identity drifted for {series_ticker}.")
            if ticker in seen_partition_tickers:
                raise ValueError(f"In-window {partition} market is duplicated for {ticker}.")
            seen_partition_tickers.add(ticker)
            prior = merged.get(ticker)
            if prior is not None and market_partition_identity(prior[1]) != market_partition_identity(market):
                raise ValueError(f"Market identity conflicts across partitions for {ticker}.")
            if prior is None or partition == "historical":
                merged[ticker] = (partition, market)

    by_date: dict[dt.date, list[dict[str, object]]] = defaultdict(list)
    event_by_date: dict[dt.date, str] = {}
    for _, market in merged.values():
        ticker = market.get("ticker")
        market_date = event_market_date(market.get("event_ticker"), series_ticker)
        event = str(market["event_ticker"])
        if market_date in event_by_date and event_by_date[market_date] != event:
            raise ValueError(f"Multiple event identities exist for {series_ticker}|{market_date}.")
        event_by_date[market_date] = event
        by_date[market_date].append(market)
    return by_date


def historical_cutoff(client: PublicClient) -> str:
    url = f"{BASE_URL}/historical/cutoff"
    payload = client.fetch(url, "historical-cutoff")
    value = payload.get("market_settled_ts")
    parse_timestamp(value, "historical market cutoff")
    return str(value)


def exact_q90_market(
    station_row: dict[str, object], event_markets: list[dict[str, object]]
) -> dict[str, object] | None:
    q90 = decimal_value(station_row["q90_f"], "Q90")
    matches = [
        market for market in event_markets
        if market.get("strike_type") == "greater"
        and market.get("floor_strike") is not None
        and decimal_value(market["floor_strike"], "floor strike") == q90
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"Exact Q90 greater contract is ambiguous for {station_row['series_ticker']}.")
    market = matches[0]
    ticker = str(market.get("ticker"))
    expected_subtitle = f"{int(q90) + 1}° or above"
    outcome_no = decimal_value(station_row["observed_high_f"], "observed high") <= q90
    if (
        q90 != q90.to_integral_value()
        or market.get("market_type") != "binary"
        or market.get("cap_strike") is not None
        or market.get("result") not in ("yes", "no")
        or market.get("yes_sub_title") != expected_subtitle
        or (market.get("result") == "no") != outcome_no
        or ("is_provisional" in market and market["is_provisional"] is not False)
        or ("mve_collection_ticker" in market and market["mve_collection_ticker"] not in (None, ""))
        or ("fee_waiver_expiration_time" in market and market["fee_waiver_expiration_time"] is not None)
    ):
        raise ValueError(f"Exact Q90 contract identity is invalid for {ticker}.")
    return market


def capture_quote(
    client: PublicClient, station_row: dict[str, object], market: dict[str, object]
) -> dict[str, object]:
    ticker = str(market["ticker"])
    market_date = dt.date.fromisoformat(str(station_row["market_date"]))
    clock = decision_clock(market_date)
    timestamp = int(clock.timestamp())
    url = (
        f"{BASE_URL}/historical/markets/{urllib.parse.quote(ticker, safe='')}/candlesticks?"
        + urllib.parse.urlencode({"start_ts": timestamp, "end_ts": timestamp, "period_interval": 1})
    )
    payload = client.fetch(url, f"{station_row['station_id']}-{market_date.isoformat()}-candle")
    if payload.get("ticker") != ticker or not isinstance(payload.get("candlesticks"), list):
        raise ValueError(f"Candle response identity is invalid for {ticker}.")
    candles = payload["candlesticks"]
    base = {
        **station_row,
        "event_ticker": market["event_ticker"],
        "market_ticker": ticker,
        "decision_at": clock.isoformat().replace("+00:00", "Z"),
        "outcome_no": int(market["result"] == "no"),
        "source_url": url,
    }
    if not candles:
        return {**base, "candidate": False, "reason": "empty_candle"}
    if len(candles) != 1 or not isinstance(candles[0], dict) or candles[0].get("end_period_ts") != timestamp:
        raise ValueError(f"Candle clock identity is invalid for {ticker}.")
    yes_bid = candles[0].get("yes_bid")
    if not isinstance(yes_bid, dict) or yes_bid.get("close") is None:
        return {**base, "candidate": False, "reason": "missing_yes_bid_close"}
    bid = decimal_value(yes_bid["close"], f"{ticker} yes bid")
    if bid <= 0 or bid >= 1:
        return {**base, "candidate": False, "reason": "boundary_yes_bid", "yes_bid": str(bid)}
    no_limit = Decimal(1) - bid
    if no_limit * 100 != (no_limit * 100).to_integral_value():
        raise ValueError(f"NO limit is not exact one-cent granularity for {ticker}.")
    edge = PROBABILITY - no_limit - fee(no_limit)
    eligible = quote_is_eligible(no_limit, edge)
    return {
        **base,
        "candidate": eligible,
        "reason": "eligible_quote" if eligible else "price_or_edge_outside_policy",
        "yes_bid": str(bid),
        "no_limit": str(no_limit),
        "fee": str(fee(no_limit)),
        "conservative_probability": str(PROBABILITY),
        "conservative_edge": f"{edge:.8f}",
    }


def fetch_executable_trade(client: PublicClient, selection: dict[str, object]) -> dict[str, object] | None:
    ticker = str(selection["market_ticker"])
    start = parse_timestamp(selection["decision_at"], f"{ticker} decision")
    end = start + dt.timedelta(minutes=5)
    query = {
        "limit": "1000", "ticker": ticker,
        "min_ts": int(start.timestamp()), "max_ts": int(end.timestamp()),
    }
    url = f"{BASE_URL}/historical/trades?{urllib.parse.urlencode(query)}"
    payload = client.fetch(url, f"{selection['station_id']}-{selection['market_date']}-trades")
    trades = payload.get("trades")
    if not isinstance(trades, list) or any(not isinstance(row, dict) for row in trades) or payload.get("cursor") not in (None, ""):
        raise ValueError(f"Historical trade response is malformed for {ticker}.")
    limit = decimal_value(selection["no_limit"], f"{ticker} NO limit")
    eligible = []
    for trade in trades:
        if trade.get("ticker") != ticker:
            raise ValueError(f"Trade ticker identity conflicts for {ticker}.")
        created = parse_timestamp(trade.get("created_time"), f"{ticker} trade time")
        if created < start or created >= end or trade.get("taker_outcome_side") != "no":
            continue
        count = decimal_value(trade.get("count_fp"), f"{ticker} trade count")
        price = decimal_value(trade.get("no_price_dollars"), f"{ticker} NO trade price")
        trade_id = trade.get("trade_id")
        if not isinstance(trade_id, str) or not trade_id or count < 1 or price > limit:
            continue
        eligible.append((created, price, trade_id, count))
    if not eligible:
        return None
    created, price, trade_id, count = sorted(eligible, key=lambda row: (row[0], row[1], row[2]))[0]
    return {
        "trade_id": trade_id,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "no_price": str(price),
        "count": str(count),
        "fee": str(fee(price)),
        "source_url": url,
    }


def clustered_lower(rows: list[dict[str, object]], value_key: str, tail: float, seed: int) -> Decimal | None:
    clusters: dict[str, list[Decimal]] = defaultdict(list)
    for row in rows:
        clusters[str(row["market_date"])].append(decimal_value(row[value_key], value_key))
    ordered = [clusters[key] for key in sorted(clusters)]
    if not ordered:
        return None
    state = seed & 0xFFFFFFFF
    means: list[Decimal] = []
    for _ in range(BOOTSTRAP_SAMPLES):
        total = Decimal(0)
        count = 0
        for _ in range(len(ordered)):
            state = (state * 1_664_525 + 1_013_904_223) & 0xFFFFFFFF
            cluster = ordered[(state * len(ordered)) // 0x1_0000_0000]
            total += sum(cluster, Decimal(0))
            count += len(cluster)
        means.append(total / Decimal(count))
    means.sort()
    return means[math.floor((BOOTSTRAP_SAMPLES - 1) * tail)]


def maximum_drawdown(returns: list[Decimal]) -> Decimal:
    cumulative = Decimal(0)
    peak = Decimal(0)
    drawdown = Decimal(0)
    for value in returns:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    return drawdown


def evaluate(client: PublicClient, quote_rows: list[dict[str, object]]) -> dict[str, object]:
    by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in quote_rows:
        if row.get("candidate") is True:
            by_date[str(row["market_date"])].append(row)
    selections = []
    for market_date in date_range(DEVELOPMENT_START, DEVELOPMENT_END):
        rows = by_date.get(market_date.isoformat(), [])
        if not rows:
            continue
        rows.sort(key=lambda row: (
            -decimal_value(row["conservative_edge"], "edge"),
            decimal_value(row["no_limit"], "NO limit"),
            str(row["market_ticker"]),
        ))
        selections.append(rows[0])
    for selection in selections:
        fill = fetch_executable_trade(client, selection)
        selection["executable_trade"] = fill
        if fill is None:
            selection["submission_return"] = "0"
            continue
        price = decimal_value(fill["no_price"], "fill price")
        trade_fee = decimal_value(fill["fee"], "fill fee")
        selection["submission_return"] = str(
            Decimal(1) - price - trade_fee if selection["outcome_no"] == 1 else -price - trade_fee
        )
    dates = {str(row["market_date"]) for row in selections}
    stations = {str(row["station_id"]) for row in selections}
    station_counts: dict[str, int] = defaultdict(int)
    for row in selections:
        station_counts[str(row["station_id"])] += 1
    returns = [decimal_value(row["submission_return"], "submission return") for row in selections]
    fills = [row for row in selections if row.get("executable_trade") is not None]
    observed = (
        sum((Decimal(row["outcome_no"]) for row in selections), Decimal(0)) / Decimal(len(selections))
        if selections else None
    )
    model_brier = (
        sum(((PROBABILITY - Decimal(row["outcome_no"])) ** 2 for row in selections), Decimal(0)) / Decimal(len(selections))
        if selections else None
    )
    price_brier = (
        sum(((decimal_value(row["no_limit"], "NO limit") - Decimal(row["outcome_no"])) ** 2 for row in selections), Decimal(0))
        / Decimal(len(selections)) if selections else None
    )
    brier_skill = (
        Decimal(1) - model_brier / price_brier
        if model_brier is not None and price_brier is not None and price_brier > 0 else None
    )
    lower90 = clustered_lower(selections, "submission_return", 0.10, 0xA11CE551) if selections else None
    holdouts = []
    for station in sorted(stations):
        rows = [row for row in selections if row["station_id"] != station]
        lower = clustered_lower(rows, "submission_return", 0.10, 0xA11CE551) if rows else None
        holdouts.append({
            "excluded_station_id": station,
            "lower_90_submission_return": f"{lower:.8f}" if lower is not None else None,
            "passes": lower is not None and lower >= 0,
        })
    realized = sum(returns, Decimal(0))
    drawdown = maximum_drawdown(returns)
    maximum_station_share = (
        Decimal(max(station_counts.values(), default=0)) / Decimal(len(selections)) if selections else Decimal(1)
    )
    reliability_error = abs(observed - PROBABILITY) if observed is not None else None
    projection = math.ceil(100 / float(lower90)) if lower90 is not None and lower90 > 0 else None
    maximum_all_in = max(
        (decimal_value(row["executable_trade"]["no_price"], "fill price") + decimal_value(row["executable_trade"]["fee"], "fill fee") for row in fills),
        default=None,
    )
    gates = {
        "thirty_selected_independent_dates": len(selections) >= 30 and len(dates) == len(selections),
        "at_least_ten_stations": len(stations) >= 10,
        "selected_reliability": reliability_error is not None and reliability_error <= Decimal("0.05"),
        "positive_brier_skill": brier_skill is not None and brier_skill > 0,
        "thirty_executable_fills": len(fills) >= 30 and len({str(row["market_date"]) for row in fills}) >= 30,
        "positive_realized_net_pnl": realized > 0,
        "drawdown_at_most_five": drawdown <= Decimal("5"),
        "clustered_90_submission_return_positive": lower90 is not None and lower90 > 0,
        "leave_one_station_out": bool(holdouts) and all(row["passes"] for row in holdouts),
        "station_concentration": maximum_station_share <= Decimal("0.15"),
        "one_selection_per_date": len(dates) == len(selections),
        "scale_250_date_clustered_95": False,
    }
    initial_names = [key for key in gates if key != "scale_250_date_clustered_95"]
    return {
        "selected_submissions": len(selections),
        "selected_independent_dates": len(dates),
        "selected_station_count": len(stations),
        "observed_success_rate": f"{observed:.8f}" if observed is not None else None,
        "reliability_error": f"{reliability_error:.8f}" if reliability_error is not None else None,
        "model_brier": f"{model_brier:.8f}" if model_brier is not None else None,
        "displayed_price_brier": f"{price_brier:.8f}" if price_brier is not None else None,
        "brier_skill": f"{brier_skill:.8f}" if brier_skill is not None else None,
        "executable_public_trades": len(fills),
        "executable_trade_dates": len({str(row["market_date"]) for row in fills}),
        "realized_net_pnl": f"{realized:.4f}",
        "maximum_drawdown": f"{drawdown:.4f}",
        "lower_90_submission_return": f"{lower90:.8f}" if lower90 is not None else None,
        "maximum_station_share": f"{maximum_station_share:.8f}",
        "maximum_date_share": f"{(Decimal(1) / Decimal(len(selections))):.8f}" if selections else None,
        "station_holdouts": holdouts,
        "projected_contracts_to_100": projection,
        "projected_gross_turnover": (
            f"{Decimal(projection) * maximum_all_in:.4f}" if projection is not None and maximum_all_in is not None else None
        ),
        "projection_is_guaranteed": False,
        "independent_oos_evidence": False,
        "capital_risk_authority": False,
        "production_activation": False,
        "gates": gates,
        "development_support_passes": all(gates[key] for key in initial_names),
        "failed_development_gates": [key for key in initial_names if not gates[key]],
        "selections": selections,
    }


def load_station_map(path: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    if file_sha256(path) != STATION_SERIES_SHA256:
        raise ValueError("Frozen station/series inventory hash is invalid.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, list) or len(payload) != 20
        or any(
            not isinstance(row, dict)
            or set(row) != {"station_id", "series_ticker"}
            or not isinstance(row["station_id"], str)
            or not row["station_id"]
            or not isinstance(row["series_ticker"], str)
            or not row["series_ticker"]
            for row in payload
        )
        or len({row["station_id"] for row in payload}) != 20
        or len({row["series_ticker"] for row in payload}) != 20
    ):
        raise ValueError("Frozen station/series inventory is malformed.")
    return payload, {row["station_id"]: row["series_ticker"] for row in payload}


def load_parent_rows(root: Path, station_to_series: dict[str, str]) -> list[dict[str, object]]:
    rows = []
    seen = set()
    for filename, expected_hash in INPUT_SHA256.items():
        path = root.parent / "nbm_qmd" / "inputs" / filename
        if file_sha256(path) != expected_hash:
            raise ValueError(f"Parent input hash is invalid: {filename}.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict) or payload.get("schema") != CAPTURE_SCHEMA
            or payload.get("research_only") is not True
            or payload.get("active_trading_capability_changed") is not False
            or payload.get("automatic_production_activation") is not False
            or not isinstance(payload.get("rows"), list)
        ):
            raise ValueError(f"Parent input identity is invalid: {filename}.")
        for source in payload["rows"]:
            if not isinstance(source, dict):
                raise ValueError("Parent row is malformed.")
            station_id = source.get("station_id")
            market_date_text = source.get("market_date")
            percentiles = source.get("percentiles")
            if (
                station_id not in station_to_series or not isinstance(market_date_text, str)
                or source.get("forecast_model") != MODEL or not isinstance(percentiles, list)
                or [row.get("probability") for row in percentiles if isinstance(row, dict)] != ["0.10", "0.25", "0.50", "0.75", "0.90"]
                or not isinstance(source.get("forecast_source_sha256"), str)
                or len(str(source["forecast_source_sha256"])) != 64
            ):
                raise ValueError("Parent row identity is malformed.")
            market_date = dt.date.fromisoformat(market_date_text)
            identity = (str(station_id), market_date)
            if identity in seen:
                raise ValueError("Parent station/date is duplicated.")
            seen.add(identity)
            q90 = decimal_value(percentiles[-1].get("max_f"), "Q90")
            observed = decimal_value(source.get("observed_high_f"), "observed high")
            rows.append({
                "station_id": station_id,
                "series_ticker": station_to_series[str(station_id)],
                "market_date": market_date.isoformat(),
                "q90_f": str(q90),
                "observed_high_f": str(observed),
                "forecast_source_sha256": source["forecast_source_sha256"],
            })
    expected_dates = set(date_range(PARENT_START, DEVELOPMENT_END))
    if len(rows) != EXPECTED_PARENT_DATES * 20 or {dt.date.fromisoformat(str(row["market_date"])) for row in rows} != expected_dates:
        raise ValueError("Parent 100-date coverage is incomplete.")
    return [row for row in rows if row["market_date"] != PARENT_START.isoformat()]


def main() -> None:
    args = parse_args()
    assert_not_production_host()
    root = Path(__file__).resolve().parent
    if file_sha256(root / "PREDECLARATION_V2.md") != PREDECLARATION_SHA256:
        raise ValueError("Frozen predeclaration hash is invalid.")
    station_rows, station_to_series = load_station_map(root / "station_series.json")
    parent_rows = load_parent_rows(root, station_to_series)
    if len(parent_rows) != EXPECTED_DEVELOPMENT_DATES * 20:
        raise ValueError("Excluded-date development coverage is invalid.")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    client = PublicClient(output_dir, args.max_requests)
    fee_identities = [validate_fee_identity(client, row["series_ticker"]) for row in station_rows]
    cutoff = historical_cutoff(client)
    rows_by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in parent_rows:
        rows_by_station[str(row["station_id"])].append(row)
    quote_rows = []
    support_funnel = {
        "parent_station_dates": len(parent_rows),
        "exact_q90_contracts": 0,
        "nonempty_candles": 0,
        "eligible_quotes": 0,
    }
    for station in station_rows:
        station_id = station["station_id"]
        series_ticker = station["series_ticker"]
        markets_by_date = discover_markets(client, series_ticker)
        for station_row in sorted(rows_by_station[station_id], key=lambda row: str(row["market_date"])):
            market_date = dt.date.fromisoformat(str(station_row["market_date"]))
            market = exact_q90_market(station_row, markets_by_date.get(market_date, []))
            if market is None:
                quote_rows.append({**station_row, "candidate": False, "reason": "no_exact_q90_greater_contract"})
                continue
            support_funnel["exact_q90_contracts"] += 1
            quoted = capture_quote(client, station_row, market)
            if quoted["reason"] != "empty_candle":
                support_funnel["nonempty_candles"] += 1
            if quoted["candidate"] is True:
                support_funnel["eligible_quotes"] += 1
            quote_rows.append(quoted)
            print(json.dumps({
                "station_id": station_id,
                "market_date": station_row["market_date"],
                "network_requests": client.used,
            }, sort_keys=True), flush=True)
    result = evaluate(client, quote_rows)
    report = {
        "schema": SCHEMA,
        "identity": IDENTITY,
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "station_series_sha256": STATION_SERIES_SHA256,
        "parent_evaluation_sha256": "8b1baa59900d28542ba176bf81548178ed9bee72129e536b72a42ab5bdc393d5",
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "independent_oos_evidence": False,
        "terminal_stage": "development_price_and_fill_audit",
        "network_policy": {
            "maximum_requests": NETWORK_LIMIT,
            "actual_requests": client.used,
            "maximum_requests_per_second": 4,
            "no_retry": True,
            "stop_on_http_429": True,
        },
        "historical_market_cutoff": cutoff,
        "market_partition_policy": {
            "live_close_start": "2026-05-08T00:00:00Z",
            "live_close_end_exclusive": "2026-08-16T00:00:00Z",
            "live_and_historical_pages_per_series": 10,
            "ignore_legacy_identity_only_outside_development_window": True,
            "require_exact_current_identity_inside_development_window": True,
        },
        "fee_identities": fee_identities,
        "support_funnel": support_funnel,
        "evaluation": result,
        "quote_rows": quote_rows,
    }
    atomic_json(output_dir / "report.json", report)
    print(json.dumps({
        "terminal_stage": report["terminal_stage"],
        "development_support_passes": result["development_support_passes"],
        "failed_development_gates": result["failed_development_gates"],
        "support_funnel": support_funnel,
        "selected_submissions": result["selected_submissions"],
        "executable_public_trades": result["executable_public_trades"],
        "realized_net_pnl": result["realized_net_pnl"],
        "network_requests": client.used,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
