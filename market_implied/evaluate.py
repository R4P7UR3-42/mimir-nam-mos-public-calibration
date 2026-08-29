#!/usr/bin/env python3
"""One-shot market-implied top-tail NO calibration and executable evaluation."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, getcontext
from pathlib import Path


getcontext().prec = 40
SCHEMA = "daily_high_top_tail_market_implied_no_evaluation_v3"
IDENTITY = "daily_high_top_tail_market_implied_no_v3"
PREDECLARATION_SHA256 = "4ffe4303b7e93af8f58fe1b0c79aae44982222cf04b2e8e37b01c65956cd94e3"
TRAINING_SERIES_SHA256 = "8779adc163f93e086ee866d89254cb99afa69da40c743631c74db9efbe4d6726"
EVALUATION_SERIES_SHA256 = "50b20f576354bafae06ab34b98c3980536a3248017e58a4142c339c1bdd144dc"
BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
TRAINING_START = dt.date(2026, 1, 12)
TRAINING_END = dt.date(2026, 3, 19)
EVALUATION_START = dt.date(2026, 3, 20)
EVALUATION_END = dt.date(2026, 6, 27)
NETWORK_LIMIT = 2_200
BOOTSTRAP_SAMPLES = 10_000
FEE_RATE = Decimal("0.07")
FEE_QUANTUM = Decimal("0.0001")
MIN_EDGE = Decimal("0.0150")
MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}
PRICE_BINS = (
    (Decimal("0.7000"), Decimal("0.8000"), False, "0.70-0.80"),
    (Decimal("0.8000"), Decimal("0.9000"), False, "0.80-0.90"),
    (Decimal("0.9000"), Decimal("0.9700"), True, "0.90-0.97"),
)


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


def event_market_date(event_ticker: object, series_ticker: str) -> dt.date:
    if not isinstance(event_ticker, str) or not event_ticker.startswith(f"{series_ticker}-"):
        raise ValueError(f"Event identity is invalid for {series_ticker}.")
    suffix = event_ticker.removeprefix(f"{series_ticker}-")
    if len(suffix) not in (6, 7) or not suffix[:2].isdigit() or suffix[2:5] not in MONTHS or not suffix[5:].isdigit():
        raise ValueError(f"Event date identity is invalid for {event_ticker}.")
    year = 2000 + int(suffix[:2])
    try:
        return dt.date(year, MONTHS[suffix[2:5]], int(suffix[5:]))
    except ValueError as error:
        raise ValueError(f"Event date is malformed for {event_ticker}.") from error


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


def price_bin(price: Decimal) -> str | None:
    for low, high, inclusive_high, label in PRICE_BINS:
        if low <= price and (price <= high if inclusive_high else price < high):
            return label
    return None


def bin_maximum(label: str) -> Decimal:
    values = {
        "0.70-0.80": Decimal("0.7999"),
        "0.80-0.90": Decimal("0.8999"),
        "0.90-0.97": Decimal("0.9700"),
    }
    return values[label]


def assert_not_production_host() -> None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/api/status", timeout=1) as response:
            payload = json.load(response)
    except (OSError, ValueError, urllib.error.URLError):
        return
    if not isinstance(payload, dict) or payload.get("environment") == "production":
        raise ValueError("Market-implied acquisition is forbidden on a production Mimir host.")


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
        request = urllib.request.Request(url, headers={"User-Agent": "mimir-market-implied-public-calibration/1"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
                headers = {key.lower(): value for key, value in response.headers.items()}
        except urllib.error.HTTPError as error:
            if error.code == 429:
                raise ValueError("Provider acquisition stopped on HTTP 429 without retry.") from error
            raise
        create_once(self.output_dir / "raw" / f"{label}.json", body)
        atomic_json(self.output_dir / "raw" / f"{label}.headers.json", headers)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as error:
            raise ValueError(f"Provider JSON is malformed for {label}.") from error
        if not isinstance(payload, dict):
            raise ValueError(f"Provider payload is not an object for {label}.")
        return payload


def validate_fee_identity(client: PublicClient, series_ticker: str, phase: str) -> dict[str, object]:
    encoded = urllib.parse.quote(series_ticker, safe="")
    series_url = f"{BASE_URL}/series/{encoded}"
    series_payload = client.fetch(series_url, f"{phase}-{series_ticker}-series")
    series = series_payload.get("series")
    if (
        not isinstance(series, dict)
        or series.get("ticker") != series_ticker
        or series.get("category") != "Climate and Weather"
        or series.get("fee_type") != "quadratic"
        or series.get("fee_multiplier") != 1
    ):
        raise ValueError(f"Fee baseline identity is invalid for {series_ticker}.")
    changes_url = (
        f"{BASE_URL}/series/fee_changes?"
        + urllib.parse.urlencode({"series_ticker": series_ticker, "show_historical": "true"})
    )
    changes_payload = client.fetch(changes_url, f"{phase}-{series_ticker}-fee-changes")
    if changes_payload != {"series_fee_change_arr": []}:
        raise ValueError(f"Fee history is not the unchanged baseline for {series_ticker}.")
    return {
        "series_ticker": series_ticker,
        "fee_type": "quadratic",
        "provider_fee_multiplier": "1",
        "base_coefficient": "0.07",
        "balance_precision": "0.0001",
        "series_url": series_url,
        "series_sha256": sha256(json.dumps(series_payload, sort_keys=True, separators=(",", ":")).encode()),
        "changes_url": changes_url,
        "changes_sha256": sha256(json.dumps(changes_payload, sort_keys=True, separators=(",", ":")).encode()),
    }


def discover_top_markets(
    client: PublicClient,
    series_ticker: str,
    start: dt.date,
    end: dt.date,
    phase: str,
    require_every_date: bool,
) -> dict[dt.date, dict[str, object]]:
    markets: list[dict[str, object]] = []
    cursor = ""
    for page in (1, 2):
        query = {"limit": "1000", "series_ticker": series_ticker}
        if cursor:
            query["cursor"] = cursor
        url = f"{BASE_URL}/historical/markets?{urllib.parse.urlencode(query)}"
        payload = client.fetch(url, f"{phase}-{series_ticker}-markets-{page}")
        page_markets = payload.get("markets")
        next_cursor = payload.get("cursor")
        if not isinstance(page_markets, list) or any(not isinstance(row, dict) for row in page_markets):
            raise ValueError(f"Historical market page is malformed for {series_ticker}.")
        if not isinstance(next_cursor, str):
            raise ValueError(f"Historical market cursor is malformed for {series_ticker}.")
        markets.extend(page_markets)
        cursor = next_cursor
        if not cursor:
            break
    if cursor:
        raise ValueError(f"Historical market pagination exceeded two pages for {series_ticker}.")
    by_event: dict[tuple[dt.date, str], list[dict[str, object]]] = defaultdict(list)
    for market in markets:
        ticker = market.get("ticker")
        if not isinstance(ticker, str) or not ticker.startswith(f"{series_ticker}-"):
            raise ValueError(f"Historical market identity drifted for {series_ticker}.")
        market_date = event_market_date(market.get("event_ticker"), series_ticker)
        if market_date < start or market_date > end:
            continue
        occurrence = market.get("occurrence_datetime")
        if occurrence is not None and parse_timestamp(occurrence, f"{ticker} occurrence").date() != market_date:
            raise ValueError(f"Occurrence date conflicts for {ticker}.")
        event = str(market["event_ticker"])
        by_event[(market_date, event)].append(market)
    top_by_date: dict[dt.date, dict[str, object]] = {}
    for (market_date, event), event_markets in by_event.items():
        if market_date in top_by_date:
            raise ValueError(f"Multiple event identities exist for {series_ticker}|{market_date}.")
        tops = [row for row in event_markets if row.get("strike_type") == "greater"]
        if len(tops) != 1:
            raise ValueError(f"Top contract identity is not unique for {event}.")
        top = tops[0]
        if (
            top.get("market_type") != "binary"
            or top.get("floor_strike") is None
            or top.get("cap_strike") is not None
            or top.get("result") not in ("yes", "no")
            or ("is_provisional" in top and top["is_provisional"] is not False)
            or ("mve_collection_ticker" in top and top["mve_collection_ticker"] not in (None, ""))
            or ("fee_waiver_expiration_time" in top and top["fee_waiver_expiration_time"] is not None)
        ):
            raise ValueError(f"Top contract is unsupported for {event}.")
        top_by_date[market_date] = top
    expected = set(date_range(start, end))
    if require_every_date and set(top_by_date) != expected:
        missing = sorted(expected - set(top_by_date))
        raise ValueError(f"Evaluation market coverage is incomplete for {series_ticker}: {missing[:5]}.")
    return top_by_date


def decision_clock(market_date: dt.date) -> dt.datetime:
    return dt.datetime.combine(market_date - dt.timedelta(days=1), dt.time(20), tzinfo=dt.timezone.utc)


def capture_quote(
    client: PublicClient,
    series_ticker: str,
    market_date: dt.date,
    market: dict[str, object],
    phase: str,
) -> dict[str, object]:
    ticker = str(market["ticker"])
    clock = decision_clock(market_date)
    timestamp = int(clock.timestamp())
    url = (
        f"{BASE_URL}/historical/markets/{urllib.parse.quote(ticker, safe='')}/candlesticks?"
        + urllib.parse.urlencode({"start_ts": timestamp, "end_ts": timestamp, "period_interval": 60})
    )
    payload = client.fetch(url, f"{phase}-{series_ticker}-{market_date.isoformat()}-candle")
    if payload.get("ticker") != ticker or not isinstance(payload.get("candlesticks"), list):
        raise ValueError(f"Candle response identity is invalid for {ticker}.")
    candles = payload["candlesticks"]
    base = {
        "series_ticker": series_ticker,
        "event_ticker": market["event_ticker"],
        "market_ticker": ticker,
        "market_date": market_date.isoformat(),
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
    label = price_bin(no_limit)
    if label is None:
        return {
            **base,
            "candidate": False,
            "reason": "outside_price_bins",
            "yes_bid": str(bid),
            "no_limit": str(no_limit),
        }
    return {
        **base,
        "candidate": True,
        "reason": "eligible_quote",
        "yes_bid": str(bid),
        "no_limit": str(no_limit),
        "fee": str(fee(no_limit)),
        "price_bin": label,
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


def calibrate(training_rows: list[dict[str, object]]) -> dict[str, object]:
    bins = []
    for index, (_, _, _, label) in enumerate(PRICE_BINS):
        rows = [row for row in training_rows if row.get("candidate") is True and row.get("price_bin") == label]
        dates = {str(row["market_date"]) for row in rows}
        for row in rows:
            row["success"] = str(row["outcome_no"])
        observed = sum((Decimal(str(row["outcome_no"])) for row in rows), Decimal(0)) / Decimal(len(rows)) if rows else None
        lower = clustered_lower(rows, "success", 0.10, 0x51A7C9E3 + index) if rows else None
        maximum = bin_maximum(label)
        conservative_edge = lower - maximum - fee(maximum) if lower is not None else None
        accepted = (
            len(rows) >= 50
            and len(dates) >= 30
            and conservative_edge is not None
            and conservative_edge >= MIN_EDGE
        )
        bins.append({
            "price_bin": label,
            "rows": len(rows),
            "independent_dates": len(dates),
            "score": str(observed.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)) if observed is not None else None,
            "lower_90_probability": f"{lower:.8f}" if lower is not None else None,
            "maximum_price": str(maximum),
            "maximum_price_fee": str(fee(maximum)),
            "minimum_conservative_edge": f"{conservative_edge:.8f}" if conservative_edge is not None else None,
            "accepted": accepted,
        })
    return {"bins": bins, "accepted_bins": [row for row in bins if row["accepted"]]}


def capture_phase(
    client: PublicClient,
    series: list[str],
    start: dt.date,
    end: dt.date,
    phase: str,
    require_every_date: bool,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    fee_identities = [validate_fee_identity(client, ticker, phase) for ticker in series]
    rows = []
    for ticker in series:
        markets = discover_top_markets(client, ticker, start, end, phase, require_every_date)
        for market_date in sorted(markets):
            rows.append(capture_quote(client, ticker, market_date, markets[market_date], phase))
            print(json.dumps({
                "phase": phase,
                "series_ticker": ticker,
                "market_date": market_date.isoformat(),
                "network_requests": client.used,
            }, sort_keys=True), flush=True)
    return rows, fee_identities


def fetch_executable_trade(
    client: PublicClient,
    selection: dict[str, object],
) -> dict[str, object] | None:
    ticker = str(selection["market_ticker"])
    start = parse_timestamp(selection["decision_at"], f"{ticker} decision")
    end = start + dt.timedelta(minutes=5)
    query = {
        "limit": "1000",
        "ticker": ticker,
        "min_ts": int(start.timestamp()),
        "max_ts": int(end.timestamp()),
    }
    url = f"{BASE_URL}/historical/trades?{urllib.parse.urlencode(query)}"
    payload = client.fetch(url, f"evaluation-{selection['series_ticker']}-{selection['market_date']}-trades")
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


def maximum_drawdown(returns: list[Decimal]) -> Decimal:
    cumulative = Decimal(0)
    peak = Decimal(0)
    drawdown = Decimal(0)
    for value in returns:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    return drawdown


def evaluate_oos(
    client: PublicClient,
    evaluation_rows: list[dict[str, object]],
    calibration: dict[str, object],
) -> dict[str, object]:
    accepted = {str(row["price_bin"]): row for row in calibration["accepted_bins"]}
    candidates: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in evaluation_rows:
        label = row.get("price_bin")
        if row.get("candidate") is not True or label not in accepted:
            continue
        model = accepted[str(label)]
        probability = decimal_value(model["lower_90_probability"], "training conservative probability")
        price = decimal_value(row["no_limit"], "decision NO limit")
        edge = probability - price - fee(price)
        if edge < MIN_EDGE:
            continue
        candidates[str(row["market_date"])].append({
            **row,
            "score": model["score"],
            "training_lower_90_probability": model["lower_90_probability"],
            "conservative_edge": f"{edge:.8f}",
        })
    selections = []
    for market_date in date_range(EVALUATION_START, EVALUATION_END):
        rows = candidates.get(market_date.isoformat(), [])
        if not rows:
            continue
        rows.sort(key=lambda row: (
            -decimal_value(row["conservative_edge"], "candidate edge"),
            decimal_value(row["no_limit"], "candidate limit"),
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
    stations = {str(row["series_ticker"]) for row in selections}
    station_counts: dict[str, int] = defaultdict(int)
    for row in selections:
        station_counts[str(row["series_ticker"])] += 1
    returns = [decimal_value(row.get("submission_return", "0"), "submission return") for row in selections]
    fills = [row for row in selections if row.get("executable_trade") is not None]
    model_brier = (
        sum((decimal_value(row["score"], "score") - Decimal(row["outcome_no"])) ** 2 for row in selections)
        / Decimal(len(selections)) if selections else None
    )
    price_brier = (
        sum((decimal_value(row["no_limit"], "NO limit") - Decimal(row["outcome_no"])) ** 2 for row in selections)
        / Decimal(len(selections)) if selections else None
    )
    brier_skill = (
        Decimal(1) - model_brier / price_brier
        if model_brier is not None and price_brier is not None and price_brier > 0 else None
    )
    reliability = []
    for label in accepted:
        rows = [row for row in selections if row["price_bin"] == label]
        bin_dates = {str(row["market_date"]) for row in rows}
        observed = sum((Decimal(row["outcome_no"]) for row in rows), Decimal(0)) / Decimal(len(rows)) if rows else None
        score = decimal_value(accepted[label]["score"], "bin score")
        error = abs(observed - score) if observed is not None else None
        reliability.append({
            "price_bin": label,
            "rows": len(rows),
            "independent_dates": len(bin_dates),
            "observed_success": f"{observed:.8f}" if observed is not None else None,
            "score": str(score),
            "absolute_error": f"{error:.8f}" if error is not None else None,
            "passes": len(bin_dates) >= 30 and error is not None and error <= Decimal("0.05"),
        })
    lower90 = clustered_lower(selections, "submission_return", 0.10, 0xA11CE551) if selections else None
    holdouts = []
    for station in sorted(stations):
        rows = [row for row in selections if row["series_ticker"] != station]
        lower = clustered_lower(rows, "submission_return", 0.10, 0xA11CE551) if rows else None
        holdouts.append({
            "excluded_series_ticker": station,
            "lower_90_submission_return": f"{lower:.8f}" if lower is not None else None,
            "passes": lower is not None and lower >= 0,
        })
    realized = sum(returns, Decimal(0))
    drawdown = maximum_drawdown(returns)
    maximum_station_share = (
        Decimal(max(station_counts.values(), default=0)) / Decimal(len(selections)) if selections else Decimal(1)
    )
    projection = math.ceil(100 / float(lower90)) if lower90 is not None and lower90 > 0 else None
    maximum_all_in = max(
        (decimal_value(row["executable_trade"]["no_price"], "fill price") + decimal_value(row["executable_trade"]["fee"], "fill fee") for row in fills),
        default=None,
    )
    gates = {
        "exact_100_date_selection": len(selections) == 100 and len(dates) == 100,
        "at_least_ten_stations": len(stations) >= 10,
        "positive_brier_skill": brier_skill is not None and brier_skill > 0,
        "reliability": bool(reliability) and all(row["passes"] for row in reliability),
        "thirty_executable_fills": len(fills) >= 30 and len({str(row["market_date"]) for row in fills}) >= 30,
        "positive_realized_net_pnl": realized > 0,
        "drawdown_at_most_five": drawdown <= Decimal("5"),
        "clustered_90_submission_return_positive": lower90 is not None and lower90 > 0,
        "leave_one_station_out": bool(holdouts) and all(row["passes"] for row in holdouts),
        "station_concentration": maximum_station_share <= Decimal("0.15"),
        "date_concentration": len(selections) == 100,
        "scale_250_date_clustered_95": False,
    }
    initial_gate_names = [key for key in gates if key != "scale_250_date_clustered_95"]
    return {
        "selected_submissions": len(selections),
        "selected_independent_dates": len(dates),
        "selected_station_count": len(stations),
        "executable_public_trades": len(fills),
        "executable_trade_dates": len({str(row["market_date"]) for row in fills}),
        "realized_net_pnl": f"{realized:.4f}",
        "maximum_drawdown": f"{drawdown:.4f}",
        "model_brier": f"{model_brier:.8f}" if model_brier is not None else None,
        "displayed_price_brier": f"{price_brier:.8f}" if price_brier is not None else None,
        "brier_skill": f"{brier_skill:.8f}" if brier_skill is not None else None,
        "lower_90_submission_return": f"{lower90:.8f}" if lower90 is not None else None,
        "maximum_station_share": f"{maximum_station_share:.8f}",
        "maximum_date_share": "0.01000000" if len(selections) == 100 else None,
        "reliability": reliability,
        "station_holdouts": holdouts,
        "projected_contracts_to_100": projection,
        "projected_gross_turnover": (
            f"{Decimal(projection) * maximum_all_in:.4f}" if projection is not None and maximum_all_in is not None else None
        ),
        "projection_is_guaranteed": False,
        "capital_risk_authority": False,
        "production_activation": False,
        "gates": gates,
        "initial_evidence_passes": all(gates[key] for key in initial_gate_names),
        "scale_evidence_passes": False,
        "failed_initial_gates": [key for key in initial_gate_names if not gates[key]],
        "selections": selections,
    }


def load_inventory(path: Path, expected_hash: str, expected_count: int) -> list[str]:
    if file_sha256(path) != expected_hash:
        raise ValueError(f"Frozen inventory hash is invalid: {path.name}.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, list)
        or len(payload) != expected_count
        or len(set(payload)) != expected_count
        or any(not isinstance(value, str) or not value.startswith("KXHIGH") for value in payload)
    ):
        raise ValueError(f"Frozen inventory is invalid: {path.name}.")
    return payload


def main() -> None:
    args = parse_args()
    assert_not_production_host()
    root = Path(__file__).resolve().parent
    if file_sha256(root / "PREDECLARATION.md") != PREDECLARATION_SHA256:
        raise ValueError("Frozen predeclaration hash is invalid.")
    training_series = load_inventory(root / "training_series.json", TRAINING_SERIES_SHA256, 5)
    evaluation_series = load_inventory(root / "evaluation_series.json", EVALUATION_SERIES_SHA256, 15)
    if set(training_series).intersection(evaluation_series):
        raise ValueError("Training and evaluation inventories overlap.")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    client = PublicClient(output_dir, args.max_requests)

    training_rows, training_fees = capture_phase(
        client, training_series, TRAINING_START, TRAINING_END, "training", False,
    )
    calibration = calibrate(training_rows)
    atomic_json(output_dir / "training.json", {
        "schema": "daily_high_top_tail_market_implied_training_v3",
        "identity": IDENTITY,
        "rows": training_rows,
        "fee_identities": training_fees,
        "calibration": calibration,
        "network_requests": client.used,
    })
    if not calibration["accepted_bins"]:
        report = {
            "schema": SCHEMA,
            "identity": IDENTITY,
            "predeclaration_sha256": PREDECLARATION_SHA256,
            "research_only": True,
            "active_trading_capability_changed": False,
            "production_database_accessed": False,
            "evaluation_series_accessed": False,
            "terminal_stage": "training_rejection",
            "network_requests": client.used,
            "calibration": calibration,
            "initial_evidence_passes": False,
            "scale_evidence_passes": False,
        }
        atomic_json(output_dir / "report.json", report)
        print(json.dumps({"terminal_stage": report["terminal_stage"], "accepted_bins": 0, "network_requests": client.used}, sort_keys=True))
        return

    evaluation_rows, evaluation_fees = capture_phase(
        client, evaluation_series, EVALUATION_START, EVALUATION_END, "evaluation", True,
    )
    result = evaluate_oos(client, evaluation_rows, calibration)
    report = {
        "schema": SCHEMA,
        "identity": IDENTITY,
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "training_series_sha256": TRAINING_SERIES_SHA256,
        "evaluation_series_sha256": EVALUATION_SERIES_SHA256,
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "evaluation_series_accessed": True,
        "terminal_stage": "oos_evaluation",
        "network_policy": {
            "maximum_requests": NETWORK_LIMIT,
            "actual_requests": client.used,
            "maximum_requests_per_second": 4,
            "no_retry": True,
            "stop_on_http_429": True,
        },
        "training_fee_identities": training_fees,
        "evaluation_fee_identities": evaluation_fees,
        "calibration": calibration,
        "evaluation": result,
    }
    atomic_json(output_dir / "report.json", report)
    print(json.dumps({
        "terminal_stage": report["terminal_stage"],
        "initial_evidence_passes": result["initial_evidence_passes"],
        "failed_initial_gates": result["failed_initial_gates"],
        "selected_submissions": result["selected_submissions"],
        "executable_public_trades": result["executable_public_trades"],
        "realized_net_pnl": result["realized_net_pnl"],
        "network_requests": client.used,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
