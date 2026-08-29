export const NOAA_NBM_QMD_CAPTURE_SCHEMA = "noaa_nbm_v5_qmd_max_t_capture_v1";
export const NOAA_NBM_QMD_MODEL = "noaa_nbm_v5_qmd_station_max_t_percentiles_v1";
export const NOAA_NBM_QMD_AVAILABLE_UPPER_BOUND_TIME = "14:15:00";
export const NOAA_NBM_QMD_PERCENTILES = [
  { field: "TXNP1", probability: "0.10" },
  { field: "TXNP2", probability: "0.25" },
  { field: "TXNP5", probability: "0.50" },
  { field: "TXNP7", probability: "0.75" },
  { field: "TXNP9", probability: "0.90" },
] as const;
