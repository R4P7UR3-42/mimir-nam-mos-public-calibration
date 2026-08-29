import datetime as dt
import importlib.util
import io
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("evaluate.py")
SPEC = importlib.util.spec_from_file_location("nbm_q90_price_evaluate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
evaluate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate)


def station_row(station: str = "KATL", market_date: str = "2026-05-08", outcome_no: int = 1):
    return {
        "station_id": station,
        "series_ticker": "KXHIGHTATL",
        "market_date": market_date,
        "q90_f": "81",
        "observed_high_f": "81" if outcome_no else "82",
        "forecast_source_sha256": "a" * 64,
    }


def exact_market(**overrides):
    market = {
        "ticker": "KXHIGHTATL-26MAY08-T81",
        "event_ticker": "KXHIGHTATL-26MAY08",
        "market_type": "binary",
        "strike_type": "greater",
        "floor_strike": 81,
        "cap_strike": None,
        "result": "no",
        "status": "finalized",
        "yes_sub_title": "82° or above",
        "is_provisional": False,
        "mve_collection_ticker": None,
        "fee_waiver_expiration_time": None,
        "_source_partition": "historical",
    }
    market.update(overrides)
    return market


class QueueClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.urls = []

    def fetch(self, url, _label):
        if not self.payloads:
            raise AssertionError("Unexpected provider request.")
        self.urls.append(url)
        return self.payloads.pop(0)


class LocalResponse(io.BytesIO):
    def __init__(self, payload, status=200):
        super().__init__(json.dumps(payload).encode())
        self.headers = {}
        self.status = status

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class NbmQ90PriceEvaluationTest(unittest.TestCase):
    def test_event_date_and_decision_clock_are_exact(self) -> None:
        self.assertEqual(
            evaluate.event_market_date("KXHIGHTATL-26MAY08", "KXHIGHTATL"),
            dt.date(2026, 5, 8),
        )
        self.assertEqual(
            evaluate.event_market_date("KXHIGHTATL-26JUN7", "KXHIGHTATL"),
            dt.date(2026, 6, 7),
        )
        self.assertEqual(
            evaluate.decision_clock(dt.date(2026, 5, 8)),
            dt.datetime(2026, 5, 7, 14, 30, tzinfo=dt.timezone.utc),
        )
        with self.assertRaises(ValueError):
            evaluate.event_market_date("KXHIGHTATL-26FOO08", "KXHIGHTATL")

    def test_fee_and_policy_boundaries_are_exact(self) -> None:
        self.assertEqual(evaluate.fee(Decimal("0.85")), Decimal("0.0090"))
        self.assertTrue(evaluate.quote_is_eligible(Decimal("0.55"), Decimal("0.0150")))
        self.assertTrue(evaluate.quote_is_eligible(Decimal("0.97"), Decimal("0.0150")))
        self.assertFalse(evaluate.quote_is_eligible(Decimal("0.5499"), Decimal("0.0150")))
        self.assertFalse(evaluate.quote_is_eligible(Decimal("0.9701"), Decimal("0.0150")))
        self.assertFalse(evaluate.quote_is_eligible(Decimal("0.90"), Decimal("0.0149")))
        with self.assertRaises(ValueError):
            evaluate.fee(Decimal("1.0001"))

    def test_exact_q90_contract_accepts_happy_path_and_fails_identity_drift(self) -> None:
        self.assertEqual(
            evaluate.exact_q90_market(station_row(), [exact_market()])["ticker"],
            "KXHIGHTATL-26MAY08-T81",
        )
        self.assertIsNone(evaluate.exact_q90_market(station_row(), [exact_market(floor_strike=82)]))
        for changed in (
            {"market_type": "scalar"},
            {"cap_strike": 82},
            {"result": "yes"},
            {"yes_sub_title": "81° or above"},
            {"is_provisional": True},
            {"mve_collection_ticker": "MVE"},
            {"fee_waiver_expiration_time": "2026-05-07T14:30:00Z"},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    evaluate.exact_q90_market(station_row(), [exact_market(**changed)])
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            evaluate.exact_q90_market(station_row(), [exact_market(), exact_market(ticker="duplicate")])

    def test_moving_partitions_ignore_only_pre_window_aliases(self) -> None:
        current = exact_market(
            ticker="KXHIGHAUS-26MAY08-T81",
            event_ticker="KXHIGHAUS-26MAY08",
        )
        legacy = exact_market(
            ticker="HIGHAUS-24OCT23-T81",
            event_ticker="HIGHAUS-24OCT23",
        )
        result = evaluate.discover_markets(QueueClient([
            {"markets": [current], "cursor": ""},
            {"markets": [current.copy(), legacy], "cursor": ""},
        ]), "KXHIGHAUS")
        self.assertEqual([row["ticker"] for row in result[dt.date(2026, 5, 8)]], [current["ticker"]])

        in_window_alias = {
            **legacy,
            "ticker": "HIGHAUS-26MAY08-T81",
            "event_ticker": "HIGHAUS-26MAY08",
        }
        with self.assertRaisesRegex(ValueError, "In-window historical market identity drifted"):
            evaluate.discover_markets(QueueClient([
                {"markets": [], "cursor": ""},
                {"markets": [in_window_alias], "cursor": ""},
            ]), "KXHIGHAUS")

    def test_partition_pagination_rejects_repeated_cursor(self) -> None:
        with self.assertRaisesRegex(ValueError, "repeated a cursor"):
            evaluate.market_pages(QueueClient([
                {"markets": [], "cursor": "same"},
                {"markets": [], "cursor": "same"},
            ]), "KXHIGHAUS", "historical")

    def test_quote_uses_only_exact_1430_yes_bid(self) -> None:
        clock = int(evaluate.decision_clock(dt.date(2026, 5, 8)).timestamp())
        client = QueueClient([{
            "ticker": "KXHIGHTATL-26MAY08-T81",
            "candlesticks": [{"end_period_ts": clock, "yes_bid": {"close": "0.0900"}}],
        }])
        quote = evaluate.capture_quote(client, station_row(), exact_market())
        self.assertTrue(quote["candidate"])
        self.assertEqual(quote["no_limit"], "0.9100")
        self.assertEqual(quote["fee"], "0.0058")
        self.assertEqual(quote["conservative_edge"], "0.01720000")
        self.assertIn("/historical/markets/", client.urls[0])

        current_client = QueueClient([{"ticker": exact_market()["ticker"], "candlesticks": []}])
        empty = evaluate.capture_quote(current_client, station_row(), {
            **exact_market(), "_source_partition": "live",
        })
        self.assertEqual(empty["reason"], "empty_candle")
        self.assertIn("/series/KXHIGHTATL/markets/", current_client.urls[0])
        with self.assertRaisesRegex(ValueError, "clock"):
            evaluate.capture_quote(
                QueueClient([{
                    "ticker": exact_market()["ticker"],
                    "candlesticks": [{"end_period_ts": clock + 60, "yes_bid": {"close": "0.0900"}}],
                }]),
                station_row(), exact_market(),
            )

    def test_executable_trade_requires_exact_window_side_count_and_limit(self) -> None:
        selection = {
            **station_row(),
            "market_ticker": exact_market()["ticker"],
            "decision_at": "2026-05-07T14:30:00Z",
            "no_limit": "0.9100",
        }
        trades = [
            {"ticker": exact_market()["ticker"], "created_time": "2026-05-07T14:29:59Z", "taker_outcome_side": "no", "count_fp": "1", "no_price_dollars": "0.90", "trade_id": "early"},
            {"ticker": exact_market()["ticker"], "created_time": "2026-05-07T14:30:01Z", "taker_outcome_side": "yes", "count_fp": "1", "no_price_dollars": "0.90", "trade_id": "wrong-side"},
            {"ticker": exact_market()["ticker"], "created_time": "2026-05-07T14:30:02Z", "taker_outcome_side": "no", "count_fp": "0.9", "no_price_dollars": "0.90", "trade_id": "too-small"},
            {"ticker": exact_market()["ticker"], "created_time": "2026-05-07T14:30:03Z", "taker_outcome_side": "no", "count_fp": "1", "no_price_dollars": "0.92", "trade_id": "too-expensive"},
            {"ticker": exact_market()["ticker"], "created_time": "2026-05-07T14:30:04Z", "taker_outcome_side": "no", "count_fp": "2", "no_price_dollars": "0.90", "trade_id": "fill"},
            {"ticker": exact_market()["ticker"], "created_time": "2026-05-07T14:35:00Z", "taker_outcome_side": "no", "count_fp": "1", "no_price_dollars": "0.80", "trade_id": "late"},
        ]
        trade_client = QueueClient([{"trades": trades, "cursor": ""}])
        result = evaluate.fetch_executable_trade(
            trade_client,
            selection,
            "2026-06-29T00:00:00Z",
        )
        self.assertEqual(result["trade_id"], "fill")
        self.assertEqual(result["fee"], "0.0063")
        self.assertIn("/historical/trades?", trade_client.urls[0])

        current_selection = {**selection, "decision_at": "2026-06-29T00:00:00Z"}
        current_client = QueueClient([{"trades": [], "cursor": ""}])
        self.assertIsNone(evaluate.fetch_executable_trade(
            current_client, current_selection, "2026-06-29T00:00:00Z",
        ))
        self.assertIn("/markets/trades?", current_client.urls[0])

    def test_development_decision_requires_every_predeclared_gate(self) -> None:
        quote_rows = []
        payloads = []
        start = dt.date(2026, 5, 8)
        for offset in range(60):
            market_date = start + dt.timedelta(days=offset)
            station = f"K{offset % 10:03d}"
            outcome_no = 0 if offset in (7, 23, 41, 57) else 1
            ticker = f"TEST-{market_date.isoformat()}"
            quote_rows.append({
                **station_row(station, market_date.isoformat(), outcome_no),
                "candidate": True,
                "market_ticker": ticker,
                "decision_at": evaluate.decision_clock(market_date).isoformat().replace("+00:00", "Z"),
                "outcome_no": outcome_no,
                "no_limit": "0.8000",
                "conservative_edge": "0.12070000",
            })
            payloads.append({"trades": [{
                "ticker": ticker,
                "created_time": evaluate.decision_clock(market_date).isoformat().replace("+00:00", "Z"),
                "taker_outcome_side": "no",
                "count_fp": "1",
                "no_price_dollars": "0.8000",
                "trade_id": f"trade-{offset}",
            }], "cursor": ""})
        result = evaluate.evaluate(QueueClient(payloads), quote_rows, "2026-06-29T00:00:00Z")
        self.assertTrue(result["development_support_passes"])
        self.assertEqual(result["failed_development_gates"], [])
        self.assertEqual(result["selected_submissions"], 60)
        self.assertEqual(result["executable_public_trades"], 60)
        self.assertGreater(Decimal(result["lower_90_submission_return"]), 0)
        self.assertFalse(result["gates"]["scale_250_date_clustered_95"])
        self.assertFalse(result["independent_oos_evidence"])
        self.assertFalse(result["capital_risk_authority"])
        self.assertFalse(result["production_activation"])

    def test_drawdown_and_request_ceiling_are_bounded(self) -> None:
        self.assertEqual(
            evaluate.maximum_drawdown([Decimal("0.10"), Decimal("-0.80"), Decimal("0.20")]),
            Decimal("0.80"),
        )
        with self.assertRaises(ValueError):
            evaluate.PublicClient(Path("/tmp/not-used"), 2_999)

    def test_public_client_persists_url_and_hash_and_production_guard_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            client = evaluate.PublicClient(Path(temporary), evaluate.NETWORK_LIMIT)
            with mock.patch.object(evaluate.urllib.request, "urlopen", return_value=LocalResponse({"ok": True})):
                self.assertEqual(client.fetch("https://example.test/source", "source"), {"ok": True})
            metadata = json.loads((Path(temporary) / "raw/source.request.json").read_text())
            self.assertEqual(metadata["request_url"], "https://example.test/source")
            self.assertEqual(metadata["request_index"], 1)
            self.assertEqual(metadata["response_sha256"], evaluate.file_sha256(Path(temporary) / "raw/source.json"))

        with mock.patch.object(
            evaluate.urllib.request,
            "urlopen",
            return_value=LocalResponse({"environment": "production"}),
        ):
            with self.assertRaisesRegex(ValueError, "forbidden"):
                evaluate.assert_not_production_host()
        with mock.patch.object(
            evaluate.urllib.request,
            "urlopen",
            return_value=LocalResponse(["malformed-status"]),
        ):
            with self.assertRaisesRegex(ValueError, "forbidden"):
                evaluate.assert_not_production_host()


if __name__ == "__main__":
    unittest.main()
