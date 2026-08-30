#!/usr/bin/env python3
"""Frozen station-specific NBM offered-tail NO development audit."""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PARENT_ROOT = ROOT.parent / "nbm_tail"
SPEC = importlib.util.spec_from_file_location("nbm_tail_v4", PARENT_ROOT / "evaluate.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load the frozen offered-tail source module.")
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)

SCHEMA = "noaa_nbm_v5_station_specific_wilson90_offered_tail_no_evaluation_v1"
IDENTITY = "noaa_nbm_v5_station_specific_wilson90_offered_tail_no_development_v1"
PREDECLARATION_SHA256 = "a97b2d3572ccce5df1b03d82537836104001ac7949cc1436e7fc825fe95cfb0c"
Z90 = Decimal("1.2815515655446004")
EXPECTED_STATION_TRAINING_ROWS = 50
MIN_EMPIRICAL = Decimal("0.920000")
MIN_SCORE = Decimal("0.9000")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-requests", type=int, required=True)
    return parser.parse_args()


def wilson_lower(successes: int, trials: int) -> Decimal:
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("Station Wilson inputs are invalid.")
    n = Decimal(trials)
    proportion = Decimal(successes) / n
    z2 = Z90 * Z90
    center = proportion + z2 / (Decimal(2) * n)
    radius = Z90 * ((proportion * (Decimal(1) - proportion) + z2 / (Decimal(4) * n)) / n).sqrt()
    return max(Decimal(0), (center - radius) / (Decimal(1) + z2 / n))


def derive_station_score_table(
    rows: list[dict[str, object]], structures: list[dict[str, object]]
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    pooled = parent.derive_score_table(rows, structures)
    stations = sorted({str(row["station_id"]) for row in rows})
    by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_station[str(row["station_id"])].append(row)
    if len(stations) != 20 or any(len(by_station[station]) != EXPECTED_STATION_TRAINING_ROWS for station in stations):
        raise ValueError("Station training coverage is not exact 20 by 50.")
    table: dict[str, dict[str, object]] = {}
    for score_key, pooled_row in sorted(pooled.items()):
        strike_type, offset_raw = score_key.split(":", 1)
        offset = parent.price.decimal_value(offset_raw, "station score offset")
        if offset != offset.to_integral_value():
            raise ValueError("Station score offset is not an exact integer.")
        for station in stations:
            station_rows = by_station[station]
            successes = sum(parent.score_outcome(row, strike_type, offset) for row in station_rows)
            empirical = Decimal(successes) / Decimal(len(station_rows))
            lower = wilson_lower(successes, len(station_rows))
            score: Decimal | None = None
            reason = str(pooled_row["reason"])
            eligible = False
            if pooled_row.get("eligible") is True and empirical < MIN_EMPIRICAL:
                reason = "station_empirical_prescreen_below_0.920000"
            elif pooled_row.get("eligible") is True:
                pooled_score = parent.price.decimal_value(pooled_row["score"], "pooled score")
                score = min(pooled_score, lower).quantize(Decimal("0.0001"), rounding=ROUND_FLOOR)
                if score > pooled_score:
                    raise ValueError("Station score exceeds its pooled ceiling.")
                eligible = score >= MIN_SCORE
                reason = "eligible_score" if eligible else "station_wilson90_score_below_0.9000"
            key = f"{station}|{score_key}"
            table[key] = {
                "station_id": station,
                "strike_type": strike_type,
                "offset_f": str(offset),
                "training_rows": len(station_rows),
                "successes": successes,
                "station_empirical_success": f"{empirical:.6f}",
                "station_wilson90_lower": f"{lower:.8f}",
                "pooled_score": pooled_row.get("score"),
                "score": f"{score:.4f}" if score is not None else None,
                "reason": reason,
                "eligible": eligible,
            }
    return table, pooled


def main() -> None:
    args = parse_args()
    parent.price.assert_not_production_host()
    if parent.price.file_sha256(ROOT / "PREDECLARATION.md") != PREDECLARATION_SHA256:
        raise ValueError("Frozen station-tail predeclaration hash is invalid.")
    rows, stations = parent.load_model_rows()
    training = parent.training_rows(rows)
    held_out_by_station: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        market_date = dt.date.fromisoformat(str(row["market_date"]))
        if parent.HELD_OUT_START <= market_date <= parent.HELD_OUT_END:
            held_out_by_station[str(row["station_id"])].append(row)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    client = parent.time_model.ResilientPublicClient(output_dir, args.max_requests)
    fee_identities = [parent.price.validate_fee_identity(client, row["series_ticker"]) for row in stations]
    cutoffs = parent.price.historical_cutoffs(client)
    offered = []
    missing_events = []
    for station in stations:
        station_id = str(station["station_id"])
        markets_by_date = parent.price.discover_markets(client, station["series_ticker"])
        for station_row in sorted(held_out_by_station[station_id], key=lambda row: str(row["market_date"])):
            market_date = dt.date.fromisoformat(str(station_row["market_date"]))
            event_markets = markets_by_date.get(market_date, [])
            tails = []
            for market in event_markets:
                structure = parent.tail_structure(station_row, market)
                if structure is not None:
                    tails.append((market, structure))
            if not event_markets:
                missing_events.append({"station_id": station_id, "market_date": str(market_date)})
                continue
            if len(tails) != 2 or {row[1]["strike_type"] for row in tails} != {"greater", "less"}:
                raise ValueError(f"Offered tail inventory is not exactly two-sided for {station_id}|{market_date}.")
            for market, structure in tails:
                offered.append((station_row, market, structure))

    score_table, pooled_score_table = derive_station_score_table(
        training, [structure for _, _, structure in offered]
    )
    reconciled = []
    outcome_conflicts = []
    for station_row, market, structure in offered:
        outcome_no, conflict = parent.provider_tail_outcome(station_row, market, structure)
        reconciled.append((station_row, market, structure, outcome_no))
        if conflict is not None:
            outcome_conflicts.append(conflict)
    if [str(row["identity"]) for row in outcome_conflicts] != [parent.EXPECTED_OUTCOME_CONFLICT]:
        raise ValueError("Held-out provider/NCEI conflict set is not the exact frozen singleton.")

    quote_rows = []
    qualified_tail_rows = 0
    for station_row, market, structure, outcome_no in reconciled:
        key = f"{station_row['station_id']}|{structure['score_key']}"
        score_row = score_table[key]
        base = {
            **station_row,
            **structure,
            "market_ticker": market["ticker"],
            "event_ticker": market["event_ticker"],
            "market_partition": market["_source_partition"],
            "clock_id": parent.DECISION_CLOCK["id"],
            "outcome_no": outcome_no,
        }
        if not score_row["eligible"]:
            quote_rows.append({**base, "candidate": False, "reason": score_row["reason"]})
            continue
        qualified_tail_rows += 1
        captured = parent.capture_tail(client, station_row, market)
        quote_rows.append(parent.apply_score({**captured, **structure}, Decimal(str(score_row["score"]))))
        print(json.dumps({
            "station_id": station_row["station_id"],
            "market_date": station_row["market_date"],
            "market_ticker": market["ticker"],
            "network_requests": client.used,
        }, sort_keys=True), flush=True)

    selections = parent.select_rows(quote_rows)
    filled = parent.time_model.attach_trades(client, selections, cutoffs["trades_created_ts"])
    evaluation = parent.evaluate_selections(filled)
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
        "training_window": {
            "start": str(parent.TRAINING_START), "end": str(parent.TRAINING_END), "rows": len(training)
        },
        "development_window": {
            "start": str(parent.HELD_OUT_START), "end": str(parent.HELD_OUT_END), "dates": 49,
            "previously_inspected": True,
        },
        "decision_clock": parent.DECISION_CLOCK,
        "score_policy": {
            "pooled_model_is_ceiling": True,
            "station_training_rows": EXPECTED_STATION_TRAINING_ROWS,
            "station_empirical_prescreen": str(MIN_EMPIRICAL),
            "station_wilson_z": str(Z90),
            "minimum_score": str(MIN_SCORE),
        },
        "price_policy": {
            "minimum": str(parent.MIN_PRICE), "maximum": str(parent.MAX_PRICE),
            "minimum_edge": str(parent.MIN_EDGE),
        },
        "network_policy": {
            "maximum_requests": parent.price.NETWORK_LIMIT,
            "actual_requests": client.used,
            "maximum_requests_per_second": 4,
            "maximum_attempts_per_logical_get": 3,
            "retry_only_transport_or_http_5xx": True,
            "no_retry_http_429_or_other_4xx": True,
        },
        "historical_cutoffs": cutoffs,
        "fee_identities": fee_identities,
        "pooled_score_table": pooled_score_table,
        "station_score_table": score_table,
        "outcome_source": "finalized_provider_market_result",
        "outcome_conflicts": outcome_conflicts,
        "support_funnel": {
            "held_out_station_dates": sum(len(value) for value in held_out_by_station.values()),
            "missing_events": len(missing_events),
            "offered_tail_rows": len(offered),
            "station_training_qualified_tail_rows": qualified_tail_rows,
            "nonempty_candles": sum(
                row.get("reason") not in (
                    "empty_candle", "empirical_prescreen_below_0.920000",
                    "station_empirical_prescreen_below_0.920000", "station_wilson90_score_below_0.9000",
                    "station_robust_score_below_0.9000",
                ) for row in quote_rows
            ),
            "displayed_prices": sum(row.get("no_limit") is not None for row in quote_rows),
            "eligible_quotes": sum(row.get("candidate") is True for row in quote_rows),
        },
        "missing_events": missing_events,
        "evaluation": evaluation,
        "quote_rows": quote_rows,
    }
    parent.price.atomic_json(output_dir / "report.json", report)
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
