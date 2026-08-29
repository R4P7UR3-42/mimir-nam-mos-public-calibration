import { Decimal } from "decimal.js";
import { decimal, ZERO } from "./decimal.ts";

export interface ClusteredValue {
  cluster: string;
  value: Decimal;
}

/**
 * Deterministic cluster bootstrap for a one-sided lower mean bound. Whole
 * clusters are resampled so correlated rows never receive IID credit.
 */
export function clusteredBootstrapLowerMean(
  rows: ClusteredValue[],
  lowerTailProbability: string,
  samples = 10_000,
): Decimal | null {
  if (rows.length === 0) return null;
  const tail = decimal(lowerTailProbability);
  if (!tail.isFinite() || tail.lte(0) || tail.gte(1)) {
    throw new Error("Cluster bootstrap lower-tail probability must be strictly between zero and one.");
  }
  if (!Number.isInteger(samples) || samples < 1 || samples > 100_000) {
    throw new Error("Cluster bootstrap samples must be an integer from one through 100000.");
  }
  const clusters = [...Map.groupBy(rows, (row) => row.cluster).entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([, values]) => values.map((row) => row.value));
  let state = 0x5a17c9e3;
  const means: number[] = [];
  for (let sample = 0; sample < samples; sample += 1) {
    let total = ZERO;
    let count = 0;
    for (let draw = 0; draw < clusters.length; draw += 1) {
      state = (Math.imul(state, 1_664_525) + 1_013_904_223) >>> 0;
      // Scale the full 32-bit state into the cluster range. Using `%` here
      // consumes only the weak low LCG bits and, for power-of-two cluster
      // counts, can make every bootstrap draw the same permutation.
      const cluster = clusters[Math.floor((state * clusters.length) / 0x1_0000_0000)];
      total = cluster.reduce((sum, value) => sum.plus(value), total);
      count += cluster.length;
    }
    means.push(total.div(count).toNumber());
  }
  means.sort((left, right) => left - right);
  return decimal(means[Math.floor((samples - 1) * tail.toNumber())]);
}
