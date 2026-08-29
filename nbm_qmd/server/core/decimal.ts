import { Decimal } from "decimal.js";

Decimal.set({
  precision: 40,
  rounding: Decimal.ROUND_HALF_UP,
  toExpNeg: -30,
  toExpPos: 30,
});

export type Decimalish = Decimal.Value;

export const ZERO = new Decimal(0);
export const ONE = new Decimal(1);
export const TWO_DP = new Decimal("0.01");
export const FOUR_DP = new Decimal("0.0001");

export function decimal(value: unknown, fallback: Decimalish = "0"): Decimal {
  if (value === null || value === undefined || value === "") {
    return new Decimal(fallback);
  }
  if (value instanceof Decimal || typeof value === "number" || typeof value === "string") {
    return new Decimal(value);
  }
  if (typeof value === "bigint") {
    return new Decimal(value.toString());
  }
  return new Decimal(fallback);
}

export function clamp(value: Decimal, low: Decimalish, high: Decimalish): Decimal {
  return Decimal.max(decimal(low), Decimal.min(decimal(high), value));
}

export function q4(value: Decimalish): Decimal {
  return decimal(value).toDecimalPlaces(4, Decimal.ROUND_HALF_UP);
}

export function ceil4(value: Decimalish): Decimal {
  return decimal(value).toDecimalPlaces(4, Decimal.ROUND_CEIL);
}

export function floor2(value: Decimalish): Decimal {
  return decimal(value).toDecimalPlaces(2, Decimal.ROUND_DOWN);
}

export function formatDecimal(value: unknown): string | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return decimal(value).toString();
}

export function average(values: Decimal[]): Decimal | null {
  if (values.length === 0) {
    return null;
  }
  return q4(values.reduce((sum, value) => sum.plus(value), ZERO).div(values.length));
}

export function ratio(numerator: number, denominator: number): Decimal {
  if (denominator === 0) {
    return ZERO;
  }
  return q4(new Decimal(numerator).div(denominator));
}
