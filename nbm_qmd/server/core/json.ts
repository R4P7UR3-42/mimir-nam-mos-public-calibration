import { Decimal } from "decimal.js";

export function jsonStringify(value: unknown): string {
  return JSON.stringify(value, (_key, item) => {
    if (item instanceof Date) {
      return item.toISOString();
    }
    if (item instanceof Decimal) {
      return item.toString();
    }
    return item;
  });
}

export function jsonParseObject(value: string | null | undefined): Record<string, unknown> {
  if (!value) {
    return {};
  }
  const parsed = JSON.parse(value);
  return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed as Record<string, unknown> : {};
}
