import { assertEquals, assertThrows } from "@std/assert";
import { decimal } from "../server/core/decimal.ts";
import { evaluateNoaaNbmQmdCalibration, noaaNbmQmdCalibrationDecision } from "./evaluate-noaa-nbm-qmd-calibration.ts";

Deno.test("NBM QMD diagnostic requires every exact gate", () => {
  const passing = {
    independentMarketDates: 100,
    positiveBrierSkill: true,
    reliabilityLevels: 5,
    everyReliabilityLevelPasses: true,
    primaryClustered90Nonnegative: true,
    primaryClustered95Nonnegative: true,
    maximumStationShare: decimal("0.05"),
    maximumDateShare: decimal("0.01"),
    leaveOneStationOutCount: 20,
    everyLeaveOneStationOutPasses: true,
  };
  assertEquals(noaaNbmQmdCalibrationDecision(passing).passes, true);
  assertEquals(noaaNbmQmdCalibrationDecision({ ...passing, independentMarketDates: 99 }).passes, false);
  assertEquals(noaaNbmQmdCalibrationDecision({ ...passing, primaryClustered95Nonnegative: false }).passes, false);
  assertEquals(noaaNbmQmdCalibrationDecision({ ...passing, maximumStationShare: decimal("0.3501") }).passes, false);
});

Deno.test("evaluates the exact 100-date five-level calibration identity", () => {
  const rows = [];
  for (let day = 0; day < 100; day += 1) {
    const date = new Date("2026-05-07T00:00:00.000Z");
    date.setUTCDate(date.getUTCDate() + day);
    const marketDate = date.toISOString().slice(0, 10);
    const run = new Date(date);
    run.setUTCDate(run.getUTCDate() - 1);
    for (let station = 0; station < 20; station += 1) {
      rows.push({
        station_id: `K${String(station).padStart(3, "0")}`,
        source_occurrences: 1,
        market_date: marketDate,
        forecast_run_initialized_at: `${run.toISOString().slice(0, 10)}T12:00:00.000Z`,
        forecast_available_at: `${run.toISOString().slice(0, 10)}T13:30:00.000Z`,
        forecast_model: "noaa_nbm_v5_qmd_station_max_t_percentiles_v1",
        mean_max_f: "50",
        standard_deviation_f: "5",
        percentiles: [
          { probability: "0.10", max_f: "10" },
          { probability: "0.25", max_f: "25" },
          { probability: "0.50", max_f: "50" },
          { probability: "0.75", max_f: "75" },
          { probability: "0.90", max_f: "95" },
        ],
        observed_high_f: String(day + 1),
        observation_source: "noaa_ncei_daily_summaries_tmax",
        observation_identity_basis: "isd_catalog_exact_icao_wban_ghcn_mapping",
        forecast_source_sha256: "a".repeat(64),
      });
    }
  }
  const result = evaluateNoaaNbmQmdCalibration({
    schema: "noaa_nbm_v5_qmd_max_t_capture_v1",
    research_only: true,
    active_trading_capability_changed: false,
    automatic_production_activation: false,
    rows,
  }, 200);
  assertEquals(result.model.diagnostic_decision.passes, true);
  assertEquals(result.model.primary_q90.observed_success_rate, "0.950000");
});

Deno.test("rejects a partial window and malformed bootstrap count", () => {
  const capture = {
    schema: "noaa_nbm_v5_qmd_max_t_capture_v1",
    research_only: true,
    active_trading_capability_changed: false,
    automatic_production_activation: false,
    rows: [],
  };
  assertThrows(() => evaluateNoaaNbmQmdCalibration(capture, 200));
  assertThrows(() => evaluateNoaaNbmQmdCalibration(capture, 0));
});
