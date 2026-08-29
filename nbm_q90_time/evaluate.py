#!/usr/bin/env python3
"""Frozen split-sample NBM Q90 pre-observation liquidity audit."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
from collections import defaultdict
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PRICE_ROOT = ROOT.parent / "nbm_q90_price"
SPEC = importlib.util.spec_from_file_location("nbm_q90_price_v3", PRICE_ROOT / "evaluate.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load the frozen Q90 source module.")
price = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(price)

SCHEMA = "noaa_nbm_v5_q90_pre_observation_liquidity_split_evaluation_v2"
IDENTITY = "noaa_nbm_v5_q90_pre_observation_liquidity_split_development_v2"
PREDECLARATION_SHA256 = "c20bbac7770b6d98c6a6e1efe79d40e22cf86954978f2d0f2a707f16c0883ad5"
PARENT_V3_SHA256 = "e12f0c642d5f7228d1ce7f5a584d6656cc9ce175c9f8b4d0efebe13068e16bde"
TRAINING_START = dt.date(2026, 5, 8)
TRAINING_END = dt.date(2026, 6, 26)
HELD_OUT_START = dt.date(2026, 6, 27)
HELD_OUT_END = dt.date(2026, 8, 14)
CLOCKS = [
    {"id": "prior_1430z", "day_offset": -1, "hour": 14, "minute": 30},
    {"id": "prior_1800z", "day_offset": -1, "hour": 18, "minute": 0},
    {"id": "prior_2100z", "day_offset": -1, "hour": 21, "minute": 0},
    {"id": "market_0000z", "day_offset": 0, "hour": 0, "minute": 0},
    {"id": "market_0300z", "day_offset": 0, "hour": 3, "minute": 0},
]


class ResilientPublicClient(price.PublicClient):
    """Bounded GET recovery with attempt-level immutable evidence."""

    def fetch(self, url: str, label: str) -> dict[str, object]:
        for attempt in range(1, 4):
            if self.used >= self.maximum:
                raise ValueError("Frozen network request ceiling exhausted.")
            delay = Decimal("0.25") - Decimal(str(price.time.monotonic() - self.last_started))
            if delay > 0:
                price.time.sleep(float(delay))
            self.last_started = price.time.monotonic()
            self.used += 1
            request = price.urllib.request.Request(
                url, headers={"User-Agent": "mimir-nbm-q90-time-public-development/2"}
            )
            try:
                with price.urllib.request.urlopen(request, timeout=60) as response:
                    body = response.read()
                    headers = {key.lower(): value for key, value in response.headers.items()}
                    status = response.getcode()
            except price.urllib.error.HTTPError as error:
                error_body = error.read()
                error_headers = {key.lower(): value for key, value in error.headers.items()}
                price.create_once(
                    self.output_dir / "raw" / f"{label}.attempt-{attempt}.http-error-body",
                    error_body,
                )
                price.atomic_json(self.output_dir / "raw" / f"{label}.attempt-{attempt}.http-error.json", {
                    "attempt": attempt,
                    "request_index": self.used,
                    "request_url": url,
                    "response_status": error.code,
                    "response_sha256": price.sha256(error_body),
                    "response_headers": error_headers,
                })
                if error.code == 429:
                    raise ValueError("Provider acquisition stopped on HTTP 429 without retry.") from error
                if error.code < 500 or error.code > 599 or attempt == 3:
                    raise
                price.time.sleep(float(attempt))
                continue
            except (price.urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
                price.atomic_json(self.output_dir / "raw" / f"{label}.attempt-{attempt}.transport-error.json", {
                    "attempt": attempt,
                    "request_index": self.used,
                    "request_url": url,
                    "error_type": type(error).__name__,
                    "diagnostic": str(error)[:240],
                })
                if attempt == 3:
                    raise ValueError("Provider transport failed after exactly three attempts.") from error
                price.time.sleep(float(attempt))
                continue
            price.create_once(self.output_dir / "raw" / f"{label}.json", body)
            price.atomic_json(self.output_dir / "raw" / f"{label}.headers.json", headers)
            price.atomic_json(self.output_dir / "raw" / f"{label}.request.json", {
                "successful_attempt": attempt,
                "request_index": self.used,
                "request_url": url,
                "response_status": status,
                "response_sha256": price.sha256(body),
            })
            try:
                payload = json.loads(body)
            except json.JSONDecodeError as error:
                raise ValueError(f"Provider JSON is malformed for {label}.") from error
            if not isinstance(payload, dict):
                raise ValueError(f"Provider payload is not an object for {label}.")
            return payload
        raise AssertionError("Unreachable bounded request state.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    return parser.parse_args()


def decision_at(market_date: dt.date, clock: dict[str, object]) -> dt.datetime:
    date = market_date + dt.timedelta(days=int(clock["day_offset"]))
    return dt.datetime.combine(
        date,
        dt.time(int(clock["hour"]), int(clock["minute"])),
        tzinfo=dt.timezone.utc,
    )


def candle_path(station_row: dict[str, object], market: dict[str, object]) -> str:
    ticker = str(market["ticker"])
    encoded_ticker = price.urllib.parse.quote(ticker, safe="")
    if market.get("_source_partition") == "historical":
        return f"historical/markets/{encoded_ticker}/candlesticks"
    if market.get("_source_partition") == "live":
        series = price.urllib.parse.quote(str(station_row["series_ticker"]), safe="")
        return f"series/{series}/markets/{encoded_ticker}/candlesticks"
    raise ValueError(f"Candle source partition is invalid for {ticker}.")


def capture_at(
    client: price.PublicClient,
    station_row: dict[str, object],
    market: dict[str, object],
    clock: dict[str, object],
) -> dict[str, object]:
    ticker = str(market["ticker"])
    market_date = dt.date.fromisoformat(str(station_row["market_date"]))
    decision = decision_at(market_date, clock)
    timestamp = int(decision.timestamp())
    query = price.urllib.parse.urlencode({
        "start_ts": timestamp,
        "end_ts": timestamp,
        "period_interval": 1,
    })
    url = f"{price.BASE_URL}/{candle_path(station_row, market)}?{query}"
    label = f"{station_row['station_id']}-{market_date}-{clock['id']}-candle"
    payload = client.fetch(url, label)
    if payload.get("ticker") != ticker or not isinstance(payload.get("candlesticks"), list):
        raise ValueError(f"Candle response identity is invalid for {ticker}|{clock['id']}.")
    candles = payload["candlesticks"]
    base = {
        **station_row,
        "event_ticker": market["event_ticker"],
        "market_ticker": ticker,
        "market_partition": market["_source_partition"],
        "clock_id": clock["id"],
        "clock_index": CLOCKS.index(clock),
        "decision_at": decision.isoformat().replace("+00:00", "Z"),
        "outcome_no": int(market["result"] == "no"),
        "source_url": url,
    }
    if not candles:
        return {**base, "candidate": False, "reason": "empty_candle"}
    if len(candles) != 1 or not isinstance(candles[0], dict) or candles[0].get("end_period_ts") != timestamp:
        raise ValueError(f"Candle clock identity is invalid for {ticker}|{clock['id']}.")
    yes_bid = candles[0].get("yes_bid")
    if not isinstance(yes_bid, dict) or yes_bid.get("close") is None:
        return {**base, "candidate": False, "reason": "missing_yes_bid_close"}
    bid = price.decimal_value(yes_bid["close"], f"{ticker} yes bid")
    if bid <= 0 or bid >= 1:
        return {**base, "candidate": False, "reason": "boundary_yes_bid", "yes_bid": str(bid)}
    no_limit = Decimal(1) - bid
    if no_limit * 100 != (no_limit * 100).to_integral_value():
        raise ValueError(f"NO limit is not exact one-cent granularity for {ticker}.")
    exact_fee = price.fee(no_limit)
    edge = price.PROBABILITY - no_limit - exact_fee
    eligible = price.quote_is_eligible(no_limit, edge)
    return {
        **base,
        "candidate": eligible,
        "reason": "eligible_quote" if eligible else "price_or_edge_outside_policy",
        "yes_bid": str(bid),
        "no_limit": str(no_limit),
        "fee": str(exact_fee),
        "conservative_probability": str(price.PROBABILITY),
        "conservative_edge": f"{edge:.8f}",
    }


def select_rows(
    clock_rows: list[dict[str, object]], clock_id: str, start: dt.date, end: dt.date
) -> list[dict[str, object]]:
    by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in clock_rows:
        market_date = dt.date.fromisoformat(str(row["market_date"]))
        if row.get("clock_id") == clock_id and row.get("candidate") is True and start <= market_date <= end:
            by_date[str(row["market_date"])].append(row)
    output = []
    for market_date in price.date_range(start, end):
        rows = by_date.get(market_date.isoformat(), [])
        if not rows:
            continue
        rows.sort(key=lambda row: (
            -price.decimal_value(row["conservative_edge"], "edge"),
            price.decimal_value(row["no_limit"], "NO limit"),
            str(row["market_ticker"]),
        ))
        output.append(dict(rows[0]))
    return output


def attach_trades(
    client: price.PublicClient, rows: list[dict[str, object]], trade_cutoff: str
) -> list[dict[str, object]]:
    output = []
    for source in rows:
        row = dict(source)
        fill = executable_trade(client, row, trade_cutoff)
        row["executable_trade"] = fill
        if fill is None:
            row["submission_return"] = "0"
        else:
            fill_price = price.decimal_value(fill["no_price"], "fill price")
            fill_fee = price.decimal_value(fill["fee"], "fill fee")
            row["submission_return"] = str(
                Decimal(1) - fill_price - fill_fee if row["outcome_no"] == 1 else -fill_price - fill_fee
            )
        output.append(row)
    return output


def executable_trade(
    client: price.PublicClient, selection: dict[str, object], trade_cutoff: str
) -> dict[str, object] | None:
    ticker = str(selection["market_ticker"])
    start = price.parse_timestamp(selection["decision_at"], f"{ticker} decision")
    end = start + dt.timedelta(minutes=5)
    cutoff = price.parse_timestamp(trade_cutoff, "historical trade cutoff")
    query = {
        "limit": "1000",
        "ticker": ticker,
        "min_ts": int(start.timestamp()),
        "max_ts": int(end.timestamp()),
    }
    path = "historical/trades" if start < cutoff else "markets/trades"
    url = f"{price.BASE_URL}/{path}?{price.urllib.parse.urlencode(query)}"
    label = f"{selection['station_id']}-{selection['market_date']}-{selection['clock_id']}-trades"
    payload = client.fetch(url, label)
    trades = payload.get("trades")
    if (
        not isinstance(trades, list)
        or any(not isinstance(row, dict) for row in trades)
        or payload.get("cursor") not in (None, "")
    ):
        raise ValueError(f"Historical trade response is malformed for {ticker}.")
    limit = price.decimal_value(selection["no_limit"], f"{ticker} NO limit")
    eligible = []
    for trade in trades:
        if trade.get("ticker") != ticker:
            raise ValueError(f"Trade ticker identity conflicts for {ticker}.")
        created = price.parse_timestamp(trade.get("created_time"), f"{ticker} trade time")
        if created < start or created >= end or trade.get("taker_outcome_side") != "no":
            continue
        count = price.decimal_value(trade.get("count_fp"), f"{ticker} trade count")
        trade_price = price.decimal_value(trade.get("no_price_dollars"), f"{ticker} NO trade price")
        trade_id = trade.get("trade_id")
        if not isinstance(trade_id, str) or not trade_id or count < 1 or trade_price > limit:
            continue
        eligible.append((created, trade_price, trade_id, count))
    if not eligible:
        return None
    created, trade_price, trade_id, count = sorted(eligible, key=lambda row: (row[0], row[1], row[2]))[0]
    return {
        "trade_id": trade_id,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "no_price": str(trade_price),
        "count": str(count),
        "fee": str(price.fee(trade_price)),
        "source_url": url,
    }


def training_diagnostic(rows: list[dict[str, object]]) -> dict[str, object]:
    fills = [row for row in rows if row.get("executable_trade") is not None]
    returns = [price.decimal_value(row["submission_return"], "submission return") for row in rows]
    stations = {str(row["station_id"]) for row in rows}
    qualified = len(rows) >= 10 and len(fills) >= 5 and len(stations) >= 5
    return {
        "selected_dates": len(rows),
        "stations": len(stations),
        "executable_fills": len(fills),
        "realized_net_pnl": f"{sum(returns, Decimal(0)):.4f}",
        "qualifies_for_clock_selection": qualified,
        "selections": rows,
    }


def held_out_diagnostic(rows: list[dict[str, object]]) -> dict[str, object]:
    dates = {str(row["market_date"]) for row in rows}
    stations = {str(row["station_id"]) for row in rows}
    fills = [row for row in rows if row.get("executable_trade") is not None]
    returns = [price.decimal_value(row["submission_return"], "submission return") for row in rows]
    observed = (
        sum((Decimal(row["outcome_no"]) for row in rows), Decimal(0)) / Decimal(len(rows)) if rows else None
    )
    model_brier = (
        sum(((price.PROBABILITY - Decimal(row["outcome_no"])) ** 2 for row in rows), Decimal(0)) / Decimal(len(rows))
        if rows else None
    )
    displayed_brier = (
        sum(((price.decimal_value(row["no_limit"], "NO limit") - Decimal(row["outcome_no"])) ** 2 for row in rows), Decimal(0))
        / Decimal(len(rows)) if rows else None
    )
    brier_skill = (
        Decimal(1) - model_brier / displayed_brier
        if model_brier is not None and displayed_brier is not None and displayed_brier > 0 else None
    )
    lower90 = price.clustered_lower(rows, "submission_return", 0.10, 0x71A3C10C) if rows else None
    station_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        station_counts[str(row["station_id"])] += 1
    holdouts = []
    for station in sorted(stations):
        remainder = [row for row in rows if row["station_id"] != station]
        lower = price.clustered_lower(remainder, "submission_return", 0.10, 0x71A3C10C) if remainder else None
        holdouts.append({
            "excluded_station_id": station,
            "lower_90_submission_return": f"{lower:.8f}" if lower is not None else None,
            "passes": lower is not None and lower >= 0,
        })
    realized = sum(returns, Decimal(0))
    drawdown = price.maximum_drawdown(returns)
    station_share = Decimal(max(station_counts.values(), default=0)) / Decimal(len(rows)) if rows else Decimal(1)
    reliability = abs(observed - price.PROBABILITY) if observed is not None else None
    gates = {
        "fifteen_selected_independent_dates": len(rows) >= 15 and len(dates) == len(rows),
        "at_least_five_stations": len(stations) >= 5,
        "selected_reliability": reliability is not None and reliability <= Decimal("0.07"),
        "positive_brier_skill": brier_skill is not None and brier_skill > 0,
        "ten_executable_fills": len(fills) >= 10 and len({str(row["market_date"]) for row in fills}) >= 10,
        "positive_realized_net_pnl": realized > 0,
        "drawdown_at_most_five": drawdown <= Decimal("5"),
        "clustered_90_submission_return_positive": lower90 is not None and lower90 > 0,
        "leave_one_station_out": bool(holdouts) and all(row["passes"] for row in holdouts),
        "station_concentration": station_share <= Decimal("0.25"),
        "one_selection_per_date": len(dates) == len(rows),
        "scale_250_date_clustered_95": False,
    }
    projection = math.ceil(100 / float(lower90)) if lower90 is not None and lower90 > 0 else None
    max_cost = max((
        price.decimal_value(row["executable_trade"]["no_price"], "fill price")
        + price.decimal_value(row["executable_trade"]["fee"], "fill fee") for row in fills
    ), default=None)
    decision_names = [key for key in gates if key != "scale_250_date_clustered_95"]
    return {
        "selected_submissions": len(rows),
        "selected_independent_dates": len(dates),
        "selected_station_count": len(stations),
        "observed_success_rate": f"{observed:.8f}" if observed is not None else None,
        "reliability_error": f"{reliability:.8f}" if reliability is not None else None,
        "brier_skill": f"{brier_skill:.8f}" if brier_skill is not None else None,
        "executable_public_trades": len(fills),
        "executable_trade_dates": len({str(row["market_date"]) for row in fills}),
        "realized_net_pnl": f"{realized:.4f}",
        "maximum_drawdown": f"{drawdown:.4f}",
        "lower_90_submission_return": f"{lower90:.8f}" if lower90 is not None else None,
        "maximum_station_share": f"{station_share:.8f}",
        "station_holdouts": holdouts,
        "projected_contracts_to_100": projection,
        "projected_gross_turnover": (
            f"{Decimal(projection) * max_cost:.4f}" if projection is not None and max_cost is not None else None
        ),
        "projection_is_guaranteed": False,
        "gates": gates,
        "development_support_passes": all(gates[key] for key in decision_names),
        "failed_development_gates": [key for key in decision_names if not gates[key]],
        "selections": rows,
    }


def main() -> None:
    args = parse_args()
    price.assert_not_production_host()
    if price.file_sha256(ROOT / "PREDECLARATION_V2.md") != PREDECLARATION_SHA256:
        raise ValueError("Frozen time-surface predeclaration hash is invalid.")
    station_rows, station_map = price.load_station_map(PRICE_ROOT / "station_series.json")
    parent_rows = price.load_parent_rows(PRICE_ROOT, station_map)
    if len(parent_rows) != 1_980:
        raise ValueError("Frozen 99-date parent coverage is invalid.")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    client = ResilientPublicClient(output_dir, args.max_requests)
    fee_identities = [price.validate_fee_identity(client, row["series_ticker"]) for row in station_rows]
    cutoffs = price.historical_cutoffs(client)
    rows_by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in parent_rows:
        rows_by_station[str(row["station_id"])].append(row)
    clock_rows = []
    exact_contracts = 0
    for station in station_rows:
        station_id = station["station_id"]
        markets_by_date = price.discover_markets(client, station["series_ticker"])
        for station_row in sorted(rows_by_station[station_id], key=lambda row: str(row["market_date"])):
            market_date = dt.date.fromisoformat(str(station_row["market_date"]))
            market = price.exact_q90_market(station_row, markets_by_date.get(market_date, []))
            if market is None:
                for clock in CLOCKS:
                    clock_rows.append({
                        **station_row,
                        "clock_id": clock["id"],
                        "clock_index": CLOCKS.index(clock),
                        "candidate": False,
                        "reason": "no_exact_q90_greater_contract",
                    })
                continue
            exact_contracts += 1
            for clock in CLOCKS:
                clock_rows.append(capture_at(client, station_row, market, clock))
            print(json.dumps({
                "station_id": station_id,
                "market_date": station_row["market_date"],
                "network_requests": client.used,
            }, sort_keys=True), flush=True)
    training = []
    for clock in CLOCKS:
        selections = select_rows(clock_rows, str(clock["id"]), TRAINING_START, TRAINING_END)
        filled = attach_trades(client, selections, cutoffs["trades_created_ts"])
        training.append({"clock": clock, **training_diagnostic(filled)})
    qualified = [row for row in training if row["qualifies_for_clock_selection"]]
    qualified.sort(key=lambda row: (
        -int(row["executable_fills"]),
        -int(row["selected_dates"]),
        -int(row["stations"]),
        int(row["clock"]["day_offset"]),
        int(row["clock"]["hour"]),
        int(row["clock"]["minute"]),
    ))
    selected_clock = qualified[0]["clock"] if qualified else None
    held_out_rows = []
    if selected_clock is not None:
        held_out_rows = attach_trades(
            client,
            select_rows(clock_rows, str(selected_clock["id"]), HELD_OUT_START, HELD_OUT_END),
            cutoffs["trades_created_ts"],
        )
    held_out = held_out_diagnostic(held_out_rows)
    per_clock_funnel = []
    for clock in CLOCKS:
        rows = [row for row in clock_rows if row.get("clock_id") == clock["id"]]
        per_clock_funnel.append({
            "clock_id": clock["id"],
            "nonempty_candles": sum(row.get("reason") != "empty_candle" and row.get("reason") != "no_exact_q90_greater_contract" for row in rows),
            "displayed_prices": sum(row.get("no_limit") is not None for row in rows),
            "eligible_quotes": sum(row.get("candidate") is True for row in rows),
        })
    report = {
        "schema": SCHEMA,
        "identity": IDENTITY,
        "predeclaration_sha256": PREDECLARATION_SHA256,
        "parent_q90_price_v3_sha256": PARENT_V3_SHA256,
        "research_only": True,
        "active_trading_capability_changed": False,
        "production_database_accessed": False,
        "independent_oos_evidence": False,
        "capital_risk_authority": False,
        "production_activation": False,
        "network_policy": {
            "maximum_requests": price.NETWORK_LIMIT,
            "actual_requests": client.used,
            "maximum_requests_per_second": 4,
            "maximum_attempts_per_logical_get": 3,
            "retry_only_transport_or_http_5xx": True,
            "retry_delays_seconds": [1, 2],
            "no_retry_http_429_or_other_4xx": True,
            "stop_on_http_429": True,
        },
        "historical_cutoffs": cutoffs,
        "clock_design": CLOCKS,
        "training_window": {"start": str(TRAINING_START), "end": str(TRAINING_END), "dates": 50},
        "held_out_window": {"start": str(HELD_OUT_START), "end": str(HELD_OUT_END), "dates": 49},
        "fee_identities": fee_identities,
        "support_funnel": {
            "parent_station_dates": len(parent_rows),
            "exact_q90_contracts": exact_contracts,
            "per_clock": per_clock_funnel,
        },
        "training_clock_diagnostics": training,
        "selected_clock": selected_clock,
        "held_out_evaluation": held_out,
        "clock_rows": clock_rows,
    }
    price.atomic_json(output_dir / "report.json", report)
    print(json.dumps({
        "selected_clock": selected_clock,
        "development_support_passes": held_out["development_support_passes"],
        "failed_development_gates": held_out["failed_development_gates"],
        "selected_submissions": held_out["selected_submissions"],
        "executable_public_trades": held_out["executable_public_trades"],
        "realized_net_pnl": held_out["realized_net_pnl"],
        "network_requests": client.used,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
