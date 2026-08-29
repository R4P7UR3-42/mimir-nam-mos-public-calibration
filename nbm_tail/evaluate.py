#!/usr/bin/env python3
"""Frozen station-robust NBM offered-tail NO split development audit."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
import re
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path


ROOT = Path(__file__).resolve().parent
Q75_ROOT = ROOT.parent / "nbm_q75"
SPEC = importlib.util.spec_from_file_location("nbm_q75_v1", Q75_ROOT / "evaluate.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load the frozen Q75 source module.")
q75 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q75)
time_model = q75.time_model
price = q75.price

SCHEMA = "noaa_nbm_v5_station_robust_offered_tail_no_split_evaluation_v4"
IDENTITY = "noaa_nbm_v5_station_robust_offered_tail_no_split_development_v4"
PREDECLARATION_SHA256 = "72156e38f7d0711c203d9b2b6af66b9e510886389c7263f598da7c3c4f7d920f"
TRAINING_START = q75.TRAINING_START
TRAINING_END = q75.TRAINING_END
HELD_OUT_START = q75.HELD_OUT_START
HELD_OUT_END = q75.HELD_OUT_END
MIN_EMPIRICAL = Decimal("0.920000")
MIN_SCORE = Decimal("0.9000")
MIN_PRICE = Decimal("0.55")
MAX_PRICE = Decimal("0.97")
MIN_EDGE = Decimal("0.0150")
DECISION_CLOCK = time_model.CLOCKS[0]
EXPECTED_OUTCOME_CONFLICT = "KMIA|2026-07-07|KXHIGHMIA-26JUL07-T88|less|88|0|no"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    return parser.parse_args()


def load_model_rows() -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    rows, stations = q75.load_q75_rows()
    by_key = {(str(row["station_id"]), str(row["market_date"])): dict(row) for row in rows}
    price_root = time_model.PRICE_ROOT
    q50_by_key: dict[tuple[str, str], str] = {}
    for filename, expected_hash in price.INPUT_SHA256.items():
        path = price_root.parent / "nbm_qmd" / "inputs" / filename
        if price.file_sha256(path) != expected_hash:
            raise ValueError(f"Parent input hash is invalid: {filename}.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload["rows"]:
            market_date = str(row["market_date"])
            if market_date == price.PARENT_START.isoformat():
                continue
            matches = [value for value in row["percentiles"] if value.get("probability") == "0.50"]
            if len(matches) != 1:
                raise ValueError("Parent Q50 percentile identity is invalid.")
            q50 = price.decimal_value(matches[0].get("max_f"), "Q50")
            if q50 != q50.to_integral_value():
                raise ValueError("Parent Q50 value is not an exact integer.")
            key = (str(row["station_id"]), market_date)
            if key in q50_by_key:
                raise ValueError("Parent Q50 station/date is duplicated.")
            q50_by_key[key] = str(q50)
    if set(q50_by_key) != set(by_key):
        raise ValueError("Parent Q50 coverage does not match the frozen 99-date window.")
    output = [{**row, "q50_f": q50_by_key[key]} for key, row in by_key.items()]
    output.sort(key=lambda row: (str(row["market_date"]), str(row["station_id"])))
    return output, stations


def training_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    for row in rows:
        market_date = dt.date.fromisoformat(str(row["market_date"]))
        if TRAINING_START <= market_date <= TRAINING_END:
            residual = (
                price.decimal_value(row["observed_high_f"], "observed high")
                - price.decimal_value(row["q50_f"], "Q50")
            )
            observed = price.decimal_value(row["observed_high_f"], "observed high")
            if observed < Decimal("-50") or observed > Decimal("140"):
                raise ValueError("Training observed high is outside the frozen physical range.")
            if residual != residual.to_integral_value():
                raise ValueError("Training residual is not an exact integer.")
            output.append({**row, "residual_f": str(residual)})
    if (
        len(output) != 1_000
        or len({str(row["market_date"]) for row in output}) != 50
        or len({str(row["station_id"]) for row in output}) != 20
    ):
        raise ValueError("Tail training coverage is not exact 50 dates by 20 stations.")
    return output


def tail_structure(station_row: dict[str, object], market: dict[str, object]) -> dict[str, object] | None:
    strike_type = market.get("strike_type")
    q50 = price.decimal_value(station_row["q50_f"], "Q50")
    if strike_type == "greater":
        if market.get("floor_strike") is None or market.get("cap_strike") is not None:
            raise ValueError(f"Greater tail strike identity is invalid for {market.get('ticker')}.")
        boundary = price.decimal_value(market["floor_strike"], "greater floor")
        expected_subtitle = f"{int(boundary) + 1}° or above"
    elif strike_type == "less":
        if market.get("cap_strike") is None or market.get("floor_strike") is not None:
            raise ValueError(f"Less tail strike identity is invalid for {market.get('ticker')}.")
        boundary = price.decimal_value(market["cap_strike"], "less cap")
        expected_subtitle = f"{int(boundary) - 1}° or below"
    else:
        return None
    if (
        boundary != boundary.to_integral_value()
        or market.get("market_type") != "binary"
        or market.get("yes_sub_title") != expected_subtitle
        or market.get("status") != "finalized"
        or ("is_provisional" in market and market["is_provisional"] is not False)
        or ("mve_collection_ticker" in market and market["mve_collection_ticker"] not in (None, ""))
        or ("fee_waiver_expiration_time" in market and market["fee_waiver_expiration_time"] is not None)
    ):
        raise ValueError(f"Tail contract structure is invalid for {market.get('ticker')}.")
    offset = boundary - q50
    if offset != offset.to_integral_value():
        raise ValueError("Tail residual boundary is not an exact integer.")
    return {
        "strike_type": strike_type,
        "boundary_f": str(boundary),
        "offset_f": str(offset),
        "score_key": f"{strike_type}:{offset}",
    }


def provider_tail_outcome(
    station_row: dict[str, object], market: dict[str, object], structure: dict[str, object]
) -> tuple[int, dict[str, object] | None]:
    high = price.decimal_value(station_row["observed_high_f"], "observed high")
    boundary = price.decimal_value(structure["boundary_f"], "tail boundary")
    if market.get("result") not in ("yes", "no"):
        raise ValueError(f"Tail provider settlement is invalid for {market.get('ticker')}.")
    provider_no = int(market.get("result") == "no")
    nws_no = int(high <= boundary if structure["strike_type"] == "greater" else high >= boundary)
    if provider_no == nws_no:
        return provider_no, None
    diagnostic = {
        "station_id": station_row["station_id"],
        "market_date": station_row["market_date"],
        "market_ticker": market["ticker"],
        "strike_type": structure["strike_type"],
        "boundary_f": str(boundary),
        "ncei_observed_high_f": str(high),
        "provider_result": market["result"],
    }
    diagnostic["identity"] = "|".join((
        str(diagnostic["station_id"]),
        str(diagnostic["market_date"]),
        str(diagnostic["market_ticker"]),
        str(diagnostic["strike_type"]),
        str(diagnostic["boundary_f"]),
        str(diagnostic["ncei_observed_high_f"]),
        str(diagnostic["provider_result"]),
    ))
    return provider_no, diagnostic


def score_outcome(row: dict[str, object], strike_type: str, offset: Decimal) -> int:
    residual = price.decimal_value(row["residual_f"], "training residual")
    return int(residual <= offset if strike_type == "greater" else residual >= offset)


def derive_score_table(
    rows: list[dict[str, object]], structures: list[dict[str, object]]
) -> dict[str, dict[str, object]]:
    keys = sorted(
        {(str(row["strike_type"]), price.decimal_value(row["offset_f"], "offset")) for row in structures},
        key=lambda row: (row[0], row[1]),
    )
    stations = sorted({str(row["station_id"]) for row in rows})
    table: dict[str, dict[str, object]] = {}
    for index, (strike_type, offset) in enumerate(keys):
        scored = [{**row, "outcome_no": score_outcome(row, strike_type, offset)} for row in rows]
        empirical = sum((Decimal(row["outcome_no"]) for row in scored), Decimal(0)) / Decimal(len(scored))
        key = f"{strike_type}:{offset}"
        if empirical < MIN_EMPIRICAL:
            table[key] = {
                "strike_type": strike_type,
                "offset_f": str(offset),
                "training_rows": len(scored),
                "empirical_success": f"{empirical:.6f}",
                "score": None,
                "reason": "empirical_prescreen_below_0.920000",
                "eligible": False,
            }
            continue
        seed = 0x7A110000 + index
        global_lower = price.clustered_lower(scored, "outcome_no", 0.10, seed)
        if global_lower is None:
            raise ValueError("Tail global clustered score is unavailable.")
        lowers = [global_lower]
        holdouts = []
        for station in stations:
            remainder = [row for row in scored if row["station_id"] != station]
            lower = price.clustered_lower(remainder, "outcome_no", 0.10, seed)
            if lower is None:
                raise ValueError("Tail station holdout score is unavailable.")
            lowers.append(lower)
            holdouts.append({"excluded_station_id": station, "lower_90_success": f"{lower:.8f}"})
        score = min(lowers).quantize(Decimal("0.0001"), rounding=ROUND_FLOOR)
        table[key] = {
            "strike_type": strike_type,
            "offset_f": str(offset),
            "training_rows": len(scored),
            "empirical_success": f"{empirical:.6f}",
            "global_lower_90_success": f"{global_lower:.8f}",
            "station_holdouts": holdouts,
            "score": f"{score:.4f}",
            "reason": "eligible_score" if score >= MIN_SCORE else "station_robust_score_below_0.9000",
            "eligible": score >= MIN_SCORE,
        }
    return table


def apply_score(row: dict[str, object], score: Decimal) -> dict[str, object]:
    if row.get("no_limit") is None:
        return {**row, "conservative_probability": f"{score:.4f}"}
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


def yes_bid_close(candle: dict[str, object], ticker: str) -> tuple[Decimal | None, str | None]:
    yes_bid = candle.get("yes_bid")
    if not isinstance(yes_bid, dict):
        return None, None
    legacy = yes_bid.get("close")
    dollars = yes_bid.get("close_dollars")
    if legacy is not None and dollars is not None:
        raise ValueError(f"Candle contains both close schemas for {ticker}.")
    if dollars is not None:
        if not isinstance(dollars, str) or re.fullmatch(r"[01]\.[0-9]{4}", dollars) is None:
            raise ValueError(f"Current dollar close is malformed for {ticker}.")
        return price.decimal_value(dollars, f"{ticker} yes bid dollars"), "close_dollars"
    if legacy is not None:
        return price.decimal_value(legacy, f"{ticker} yes bid legacy"), "close"
    return None, None


def capture_tail(
    client: price.PublicClient,
    station_row: dict[str, object],
    market: dict[str, object],
) -> dict[str, object]:
    ticker = str(market["ticker"])
    market_date = dt.date.fromisoformat(str(station_row["market_date"]))
    decision = time_model.decision_at(market_date, DECISION_CLOCK)
    timestamp = int(decision.timestamp())
    query = price.urllib.parse.urlencode({
        "start_ts": timestamp,
        "end_ts": timestamp,
        "period_interval": 1,
    })
    url = f"{price.BASE_URL}/{time_model.candle_path(station_row, market)}?{query}"
    label = f"{station_row['station_id']}-{ticker}-{market_date}-{DECISION_CLOCK['id']}-candle"
    payload = client.fetch(url, label)
    if payload.get("ticker") != ticker or not isinstance(payload.get("candlesticks"), list):
        raise ValueError(f"Candle response identity is invalid for {ticker}.")
    candles = payload["candlesticks"]
    base = {
        **station_row,
        "event_ticker": market["event_ticker"],
        "market_ticker": ticker,
        "market_partition": market["_source_partition"],
        "clock_id": DECISION_CLOCK["id"],
        "clock_index": time_model.CLOCKS.index(DECISION_CLOCK),
        "decision_at": decision.isoformat().replace("+00:00", "Z"),
        "outcome_no": int(market["result"] == "no"),
        "source_url": url,
    }
    if not candles:
        return {**base, "candidate": False, "reason": "empty_candle"}
    if len(candles) != 1 or not isinstance(candles[0], dict) or candles[0].get("end_period_ts") != timestamp:
        raise ValueError(f"Candle clock identity is invalid for {ticker}.")
    bid, schema = yes_bid_close(candles[0], ticker)
    if bid is None:
        return {**base, "candidate": False, "reason": "missing_yes_bid_close"}
    if bid <= 0 or bid >= 1:
        return {**base, "candidate": False, "reason": "boundary_yes_bid", "yes_bid": str(bid), "yes_bid_schema": schema}
    no_limit = Decimal(1) - bid
    if no_limit * 100 != (no_limit * 100).to_integral_value():
        raise ValueError(f"NO limit is not exact one-cent granularity for {ticker}.")
    return {
        **base,
        "candidate": False,
        "reason": "unscored_quote",
        "yes_bid": str(bid),
        "yes_bid_schema": schema,
        "no_limit": str(no_limit),
    }


def select_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_date: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        market_date = dt.date.fromisoformat(str(row["market_date"]))
        if row.get("candidate") is True and HELD_OUT_START <= market_date <= HELD_OUT_END:
            by_date[str(row["market_date"])].append(row)
    output = []
    for market_date in price.date_range(HELD_OUT_START, HELD_OUT_END):
        candidates = by_date.get(str(market_date), [])
        if not candidates:
            continue
        candidates.sort(key=lambda row: (
            -price.decimal_value(row["conservative_edge"], "edge"),
            -price.decimal_value(row["conservative_probability"], "score"),
            price.decimal_value(row["no_limit"], "NO limit"),
            str(row["market_ticker"]),
        ))
        output.append(dict(candidates[0]))
    return output


def evaluate_selections(rows: list[dict[str, object]]) -> dict[str, object]:
    dates = {str(row["market_date"]) for row in rows}
    stations = {str(row["station_id"]) for row in rows}
    fills = [row for row in rows if row.get("executable_trade") is not None]
    returns = [price.decimal_value(row["submission_return"], "submission return") for row in rows]
    outcomes = [Decimal(row["outcome_no"]) for row in rows]
    scores = [price.decimal_value(row["conservative_probability"], "score") for row in rows]
    limits = [price.decimal_value(row["no_limit"], "NO limit") for row in rows]
    observed = sum(outcomes, Decimal(0)) / Decimal(len(rows)) if rows else None
    mean_score = sum(scores, Decimal(0)) / Decimal(len(rows)) if rows else None
    model_brier = (
        sum(((scores[index] - outcomes[index]) ** 2 for index in range(len(rows))), Decimal(0)) / Decimal(len(rows))
        if rows else None
    )
    displayed_brier = (
        sum(((limits[index] - outcomes[index]) ** 2 for index in range(len(rows))), Decimal(0)) / Decimal(len(rows))
        if rows else None
    )
    brier_skill = (
        Decimal(1) - model_brier / displayed_brier
        if model_brier is not None and displayed_brier is not None and displayed_brier > 0 else None
    )
    reliability = abs(observed - mean_score) if observed is not None and mean_score is not None else None
    lower90 = price.clustered_lower(rows, "submission_return", 0.10, 0x7A11C10C) if rows else None
    station_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        station_counts[str(row["station_id"])] += 1
    holdouts = []
    for station in sorted(stations):
        remainder = [row for row in rows if row["station_id"] != station]
        lower = price.clustered_lower(remainder, "submission_return", 0.10, 0x7A11C10C) if remainder else None
        holdouts.append({
            "excluded_station_id": station,
            "lower_90_submission_return": f"{lower:.8f}" if lower is not None else None,
            "passes": lower is not None and lower >= 0,
        })
    realized = sum(returns, Decimal(0))
    drawdown = price.maximum_drawdown(returns)
    station_share = Decimal(max(station_counts.values(), default=0)) / Decimal(len(rows)) if rows else Decimal(1)
    gates = {
        "thirty_selected_independent_dates": len(rows) >= 30 and len(dates) == len(rows),
        "at_least_ten_stations": len(stations) >= 10,
        "selected_reliability": reliability is not None and reliability <= Decimal("0.05"),
        "positive_brier_skill": brier_skill is not None and brier_skill > 0,
        "thirty_executable_fills": len(fills) >= 30 and len({str(row["market_date"]) for row in fills}) >= 30,
        "positive_realized_net_pnl": realized > 0,
        "drawdown_at_most_five": drawdown <= Decimal("5"),
        "clustered_90_submission_return_positive": lower90 is not None and lower90 > 0,
        "leave_one_station_out": bool(holdouts) and all(row["passes"] for row in holdouts),
        "station_concentration": station_share <= Decimal("0.15"),
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
        "mean_conservative_score": f"{mean_score:.8f}" if mean_score is not None else None,
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
        "projected_gross_turnover": f"{Decimal(projection) * max_cost:.4f}" if projection and max_cost else None,
        "projection_is_guaranteed": False,
        "gates": gates,
        "development_support_passes": all(gates[key] for key in decision_names),
        "failed_development_gates": [key for key in decision_names if not gates[key]],
        "selections": rows,
    }


def main() -> None:
    args = parse_args()
    price.assert_not_production_host()
    if price.file_sha256(ROOT / "PREDECLARATION_V4.md") != PREDECLARATION_SHA256:
        raise ValueError("Frozen tail predeclaration hash is invalid.")
    rows, stations = load_model_rows()
    training = training_rows(rows)
    held_out_by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        market_date = dt.date.fromisoformat(str(row["market_date"]))
        if HELD_OUT_START <= market_date <= HELD_OUT_END:
            held_out_by_station[str(row["station_id"])].append(row)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    client = time_model.ResilientPublicClient(output_dir, args.max_requests)
    fee_identities = [price.validate_fee_identity(client, row["series_ticker"]) for row in stations]
    cutoffs = price.historical_cutoffs(client)
    offered = []
    missing_events = []
    for station in stations:
        station_id = station["station_id"]
        markets_by_date = price.discover_markets(client, station["series_ticker"])
        for station_row in sorted(held_out_by_station[station_id], key=lambda row: str(row["market_date"])):
            market_date = dt.date.fromisoformat(str(station_row["market_date"]))
            event_markets = markets_by_date.get(market_date, [])
            tails = []
            for market in event_markets:
                structure = tail_structure(station_row, market)
                if structure is not None:
                    tails.append((market, structure))
            if not event_markets:
                missing_events.append({"station_id": station_id, "market_date": str(market_date)})
                continue
            if len(tails) != 2 or {row[1]["strike_type"] for row in tails} != {"greater", "less"}:
                raise ValueError(f"Offered tail inventory is not exactly two-sided for {station_id}|{market_date}.")
            for market, structure in tails:
                offered.append((station_row, market, structure))
    score_table = derive_score_table(training, [structure for _, _, structure in offered])
    reconciled = []
    outcome_conflicts = []
    for station_row, market, structure in offered:
        outcome_no, conflict = provider_tail_outcome(station_row, market, structure)
        reconciled.append((station_row, market, structure, outcome_no))
        if conflict is not None:
            outcome_conflicts.append(conflict)
    if [str(row["identity"]) for row in outcome_conflicts] != [EXPECTED_OUTCOME_CONFLICT]:
        raise ValueError("Held-out provider/NCEI conflict set is not the exact frozen singleton.")
    quote_rows = []
    qualified_tail_rows = 0
    for station_row, market, structure, outcome_no in reconciled:
        score_row = score_table[str(structure["score_key"])]
        base = {
            **station_row,
            **structure,
            "market_ticker": market["ticker"],
            "event_ticker": market["event_ticker"],
            "market_partition": market["_source_partition"],
            "clock_id": DECISION_CLOCK["id"],
            "outcome_no": outcome_no,
        }
        if not score_row["eligible"]:
            quote_rows.append({**base, "candidate": False, "reason": score_row["reason"]})
            continue
        qualified_tail_rows += 1
        captured = capture_tail(client, station_row, market)
        quote_rows.append(apply_score({**captured, **structure}, Decimal(str(score_row["score"]))))
        print(json.dumps({
            "station_id": station_row["station_id"],
            "market_date": station_row["market_date"],
            "market_ticker": market["ticker"],
            "network_requests": client.used,
        }, sort_keys=True), flush=True)
    selections = select_rows(quote_rows)
    filled = time_model.attach_trades(client, selections, cutoffs["trades_created_ts"])
    evaluation = evaluate_selections(filled)
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
        "training_window": {"start": str(TRAINING_START), "end": str(TRAINING_END), "rows": len(training)},
        "held_out_window": {"start": str(HELD_OUT_START), "end": str(HELD_OUT_END), "dates": 49},
        "decision_clock": DECISION_CLOCK,
        "score_policy": {"empirical_prescreen": str(MIN_EMPIRICAL), "minimum_score": str(MIN_SCORE)},
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
        "score_table": score_table,
        "outcome_source": "finalized_provider_market_result",
        "outcome_conflicts": outcome_conflicts,
        "support_funnel": {
            "held_out_station_dates": sum(len(value) for value in held_out_by_station.values()),
            "missing_events": len(missing_events),
            "offered_tail_rows": len(offered),
            "training_qualified_tail_rows": qualified_tail_rows,
            "nonempty_candles": sum(
                row.get("reason") not in ("empty_candle", "empirical_prescreen_below_0.920000", "station_robust_score_below_0.9000")
                for row in quote_rows
            ),
            "displayed_prices": sum(row.get("no_limit") is not None for row in quote_rows),
            "eligible_quotes": sum(row.get("candidate") is True for row in quote_rows),
        },
        "missing_events": missing_events,
        "evaluation": evaluation,
        "quote_rows": quote_rows,
    }
    price.atomic_json(output_dir / "report.json", report)
    print(json.dumps({
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
