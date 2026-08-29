import { decimal } from "../server/core/decimal.ts";
import { jsonParseObject, jsonStringify } from "../server/core/json.ts";
import { clusteredBootstrapLowerMean } from "../server/core/statistics.ts";
import {
  NOAA_NBM_QMD_AVAILABLE_UPPER_BOUND_TIME,
  NOAA_NBM_QMD_CAPTURE_SCHEMA,
  NOAA_NBM_QMD_MODEL,
  NOAA_NBM_QMD_PERCENTILES,
} from "./nbm-qmd-constants.ts";

export const NOAA_NBM_QMD_EVALUATION_SCHEMA = "noaa_nbm_v5_qmd_max_t_calibration_evaluation_v1";
export const NOAA_NBM_QMD_EVALUATION_START = "2026-05-07";
export const NOAA_NBM_QMD_EVALUATION_END = "2026-08-14";
export const NOAA_NBM_QMD_EXPECTED_DATES = 100;
export const NOAA_NBM_QMD_PRIMARY_SCORE = "0.90";
export const NOAA_NBM_QMD_MAXIMUM_ABSOLUTE_RELIABILITY_ERROR = "0.05";

interface Args {
  inputs: string[];
  output: string | null;
}

interface CaptureRow {
  station_id: string;
  source_occurrences: number;
  market_date: string;
  forecast_run_initialized_at: string;
  forecast_available_at: string;
  forecast_model: string;
  mean_max_f: string;
  standard_deviation_f: string;
  percentiles: Array<{ probability: string; max_f: string }>;
  observed_high_f: string;
  observation_source: string;
  observation_identity_basis: string;
  forecast_source_sha256: string;
}

interface Prediction {
  stationId: string;
  marketDate: string;
  score: ReturnType<typeof decimal>;
  outcome: ReturnType<typeof decimal>;
}

if (import.meta.main) {
  const args = parseArgs(Deno.args);
  const captures = await Promise.all(args.inputs.map(async (path) => jsonParseObject(await Deno.readTextFile(path))));
  const report = evaluateNoaaNbmQmdCalibration(captures);
  if (args.output) await Deno.writeTextFile(args.output, `${jsonStringify(report)}\n`);
  console.log(jsonStringify(report));
}

export function evaluateNoaaNbmQmdCalibration(payloads: unknown | unknown[], bootstrapSamples = 10_000) {
  if (!Number.isInteger(bootstrapSamples) || bootstrapSamples < 1 || bootstrapSamples > 100_000) {
    throw new Error("NOAA NBM QMD bootstrap sample count is invalid.");
  }
  const roots = Array.isArray(payloads) ? payloads : [payloads];
  if (!roots.length) throw new Error("NOAA NBM QMD evaluation requires at least one capture.");
  const rows = roots.flatMap(parseCaptureRows);
  const byIdentity = new Map<string, CaptureRow>();
  for (const row of rows) {
    const identity = `${row.station_id}|${row.market_date}`;
    if (byIdentity.has(identity)) throw new Error("NOAA NBM QMD evaluation contains a duplicate station/date.");
    byIdentity.set(identity, row);
  }
  const sorted = [...byIdentity.values()].sort((left, right) =>
    left.market_date.localeCompare(right.market_date) || left.station_id.localeCompare(right.station_id)
  );
  const dates = [...new Set(sorted.map((row) => row.market_date))];
  const stations = [...new Set(sorted.map((row) => row.station_id))];
  if (
    dates.length !== NOAA_NBM_QMD_EXPECTED_DATES || dates[0] !== NOAA_NBM_QMD_EVALUATION_START ||
    dates.at(-1) !== NOAA_NBM_QMD_EVALUATION_END ||
    dates.some((date, index) => index > 0 && shiftDate(dates[index - 1], 1) !== date)
  ) throw new Error("NOAA NBM QMD evaluation window is incomplete or not the frozen date range.");
  if (stations.length !== 20 || sorted.length !== dates.length * stations.length) {
    throw new Error("NOAA NBM QMD evaluation station/date coverage is incomplete.");
  }

  const predictions = sorted.flatMap((row) =>
    row.percentiles.map((percentile) => ({
      stationId: row.station_id,
      marketDate: row.market_date,
      score: decimal(percentile.probability),
      outcome: decimal(row.observed_high_f).lte(percentile.max_f) ? decimal(1) : decimal(0),
    }))
  );
  const observedRate = mean(predictions.map((row) => row.outcome));
  const brier = mean(predictions.map((row) => row.score.minus(row.outcome).pow(2)));
  const climatologyBrier = observedRate ? mean(predictions.map((row) => observedRate.minus(row.outcome).pow(2))) : null;
  const brierSkill = brier && climatologyBrier && !climatologyBrier.eq(0)
    ? decimal(1).minus(brier.div(climatologyBrier))
    : null;
  const reliability = NOAA_NBM_QMD_PERCENTILES.map((definition) => {
    const levelRows = predictions.filter((row) => row.score.eq(definition.probability));
    const observed = mean(levelRows.map((row) => row.outcome));
    const margin = observed?.minus(definition.probability) ?? null;
    return {
      probability: definition.probability,
      predictions: levelRows.length,
      independent_market_dates: new Set(levelRows.map((row) => row.marketDate)).size,
      observed_success_rate: observed?.toFixed(6) ?? null,
      observed_minus_score: margin?.toFixed(6) ?? null,
      absolute_error_at_most_0_05: margin?.abs().lte(NOAA_NBM_QMD_MAXIMUM_ABSOLUTE_RELIABILITY_ERROR) === true,
    };
  });
  const primary = predictions.filter((row) => row.score.eq(NOAA_NBM_QMD_PRIMARY_SCORE));
  const primaryMarginRows = primary.map((row) => ({
    cluster: row.marketDate,
    value: row.outcome.minus(row.score),
  }));
  const primaryObserved = mean(primary.map((row) => row.outcome));
  const primaryClustered90 = clusteredBootstrapLowerMean(primaryMarginRows, "0.10", bootstrapSamples);
  const primaryClustered95 = clusteredBootstrapLowerMean(primaryMarginRows, "0.05", bootstrapSamples);
  const leaveOneStationOut = stations.sort().map((excludedStation) => {
    const selected = primary.filter((row) => row.stationId !== excludedStation);
    const margin = mean(selected.map((row) => row.outcome.minus(row.score)));
    const lower = clusteredBootstrapLowerMean(
      selected.map((row) => ({ cluster: row.marketDate, value: row.outcome.minus(row.score) })),
      "0.05",
      bootstrapSamples,
    );
    return {
      excluded_station: excludedStation,
      predictions: selected.length,
      independent_market_dates: new Set(selected.map((row) => row.marketDate)).size,
      observed_minus_score: margin?.toFixed(6) ?? null,
      one_sided_95_date_clustered_lower_observed_minus_score: lower?.toFixed(6) ?? null,
      passes: margin?.gte(0) === true && lower?.gte(0) === true,
    };
  });
  const decision = noaaNbmQmdCalibrationDecision({
    independentMarketDates: dates.length,
    positiveBrierSkill: brierSkill?.gt(0) === true,
    reliabilityLevels: reliability.length,
    everyReliabilityLevelPasses: reliability.every((row) => row.absolute_error_at_most_0_05),
    primaryClustered90Nonnegative: primaryClustered90?.gte(0) === true,
    primaryClustered95Nonnegative: primaryClustered95?.gte(0) === true,
    maximumStationShare: maximumShare(primary.map((row) => row.stationId)),
    maximumDateShare: maximumShare(primary.map((row) => row.marketDate)),
    leaveOneStationOutCount: leaveOneStationOut.length,
    everyLeaveOneStationOutPasses: leaveOneStationOut.every((row) => row.passes),
  });
  return {
    schema: NOAA_NBM_QMD_EVALUATION_SCHEMA,
    generated_at: new Date().toISOString(),
    research_only: true,
    active_trading_capability_changed: false,
    automatic_production_activation: false,
    design: {
      model: NOAA_NBM_QMD_MODEL,
      evaluation_start_market_date: NOAA_NBM_QMD_EVALUATION_START,
      evaluation_end_market_date: NOAA_NBM_QMD_EVALUATION_END,
      evaluation_independent_market_dates: NOAA_NBM_QMD_EXPECTED_DATES,
      probability_levels: NOAA_NBM_QMD_PERCENTILES.map((row) => row.probability),
      primary_trading_hypothesis_probability: NOAA_NBM_QMD_PRIMARY_SCORE,
      maximum_absolute_reliability_error: NOAA_NBM_QMD_MAXIMUM_ABSOLUTE_RELIABILITY_ERROR,
      date_clustered: true,
      no_probability_fitting: true,
    },
    model: {
      predictions: predictions.length,
      stations: stations.length,
      independent_market_dates: dates.length,
      brier_score: brier?.toFixed(6) ?? null,
      climatology_brier_score: climatologyBrier?.toFixed(6) ?? null,
      brier_skill_versus_evaluation_climatology: brierSkill?.toFixed(6) ?? null,
      reliability,
      primary_q90: {
        predictions: primary.length,
        observed_success_rate: primaryObserved?.toFixed(6) ?? null,
        observed_minus_score: primaryObserved?.minus(NOAA_NBM_QMD_PRIMARY_SCORE).toFixed(6) ?? null,
        one_sided_90_date_clustered_lower_observed_minus_score: primaryClustered90?.toFixed(6) ?? null,
        one_sided_95_date_clustered_lower_observed_minus_score: primaryClustered95?.toFixed(6) ?? null,
        maximum_station_share: maximumShare(primary.map((row) => row.stationId)).toFixed(4),
        maximum_date_share: maximumShare(primary.map((row) => row.marketDate)).toFixed(4),
      },
      leave_one_station_out_primary_q90: leaveOneStationOut,
      diagnostic_decision: decision,
    },
    limitations: [
      "This is a frozen forecast-calibration diagnostic, not quote, depth, fill, fee, P&L, policy, cohort, capital, or order evidence.",
      "Five percentile events per station/date are dependent; inference and gates use whole market dates and station holdouts.",
      "Displayed integer percentile values can be conservative under discrete temperature outcomes and still require exact CLI settlement compatibility.",
      "Only a passing result may advance to a separate consumed-date price-support diagnostic and future prospective execution ledger.",
    ],
  };
}

export function noaaNbmQmdCalibrationDecision(input: {
  independentMarketDates: number;
  positiveBrierSkill: boolean;
  reliabilityLevels: number;
  everyReliabilityLevelPasses: boolean;
  primaryClustered90Nonnegative: boolean;
  primaryClustered95Nonnegative: boolean;
  maximumStationShare: ReturnType<typeof decimal>;
  maximumDateShare: ReturnType<typeof decimal>;
  leaveOneStationOutCount: number;
  everyLeaveOneStationOutPasses: boolean;
}) {
  const gates = {
    exact_100_independent_market_dates: input.independentMarketDates === NOAA_NBM_QMD_EXPECTED_DATES,
    positive_brier_skill: input.positiveBrierSkill,
    exact_five_reliability_levels: input.reliabilityLevels === NOAA_NBM_QMD_PERCENTILES.length,
    every_reliability_level_within_0_05: input.everyReliabilityLevelPasses,
    primary_q90_clustered_90_nonnegative: input.primaryClustered90Nonnegative,
    primary_q90_clustered_95_nonnegative: input.primaryClustered95Nonnegative,
    station_concentration: input.maximumStationShare.lte("0.35"),
    date_concentration: input.maximumDateShare.lte("0.05"),
    leave_one_station_out_coverage: input.leaveOneStationOutCount >= 2,
    every_leave_one_station_out_primary_q90_passes: input.everyLeaveOneStationOutPasses,
  };
  return { passes: Object.values(gates).every(Boolean), gates };
}

function parseCaptureRows(payload: unknown): CaptureRow[] {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("NOAA NBM QMD capture is malformed.");
  }
  const root = payload as Record<string, unknown>;
  if (
    root.schema !== NOAA_NBM_QMD_CAPTURE_SCHEMA || root.research_only !== true ||
    root.active_trading_capability_changed !== false || root.automatic_production_activation !== false ||
    !Array.isArray(root.rows)
  ) throw new Error("NOAA NBM QMD capture identity is not research-only.");
  const rows = root.rows as CaptureRow[];
  for (const row of rows) {
    const runDate = shiftDate(row.market_date, -1);
    const availableAt = new Date(row.forecast_available_at);
    if (
      !row.station_id || !Number.isInteger(row.source_occurrences) || row.source_occurrences < 1 ||
      !/^\d{4}-\d{2}-\d{2}$/.test(row.market_date) ||
      row.forecast_run_initialized_at !== `${runDate}T12:00:00.000Z` || Number.isNaN(availableAt.getTime()) ||
      availableAt < new Date(`${runDate}T12:00:00.000Z`) ||
      availableAt > new Date(`${runDate}T${NOAA_NBM_QMD_AVAILABLE_UPPER_BOUND_TIME}.000Z`) ||
      row.forecast_model !== NOAA_NBM_QMD_MODEL || !decimal(row.mean_max_f).isFinite() ||
      !decimal(row.standard_deviation_f).isFinite() || decimal(row.standard_deviation_f).lt(0) ||
      !decimal(row.observed_high_f).isFinite() || row.observation_source !== "noaa_ncei_daily_summaries_tmax" ||
      !["ncei_daily_summary_metadata", "isd_catalog_exact_icao_wban_ghcn_mapping"].includes(
        row.observation_identity_basis,
      ) ||
      !/^[0-9a-f]{64}$/.test(row.forecast_source_sha256) ||
      !Array.isArray(row.percentiles) || row.percentiles.length !== NOAA_NBM_QMD_PERCENTILES.length ||
      row.percentiles.some((value, index) =>
        value.probability !== NOAA_NBM_QMD_PERCENTILES[index].probability || !decimal(value.max_f).isFinite() ||
        (index > 0 && decimal(value.max_f).lt(row.percentiles[index - 1].max_f))
      )
    ) throw new Error("NOAA NBM QMD capture row is malformed.");
  }
  return rows;
}

function mean(values: ReturnType<typeof decimal>[]) {
  return values.length ? values.reduce((sum, value) => sum.plus(value), decimal(0)).div(values.length) : null;
}

function maximumShare(values: string[]) {
  if (!values.length) return decimal(0);
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  return decimal(Math.max(...counts.values())).div(values.length);
}

function shiftDate(value: string, days: number) {
  const date = new Date(`${value}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function parseArgs(raw: string[]): Args {
  const args = raw[0] === "--" ? raw.slice(1) : raw;
  const inputs: string[] = [];
  let output: string | null = null;
  for (let index = 0; index < args.length; index += 2) {
    const key = args[index];
    const value = args[index + 1];
    if (!key?.startsWith("--") || value === undefined) throw new Error(`Malformed argument near ${key ?? "end"}.`);
    if (key === "--input") inputs.push(value);
    else if (key === "--output") output = value;
    else throw new Error(`Unknown argument ${key}.`);
  }
  if (!inputs.length) throw new Error("At least one --input is required.");
  return { inputs, output };
}
