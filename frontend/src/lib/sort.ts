export type SortDirection = "asc" | "desc" | null;

export interface SortState {
  key: string;
  direction: SortDirection;
}

/**
 * Cycles sort direction: null -> asc -> desc -> null
 */
export function nextSortDirection(current: SortDirection): SortDirection {
  if (current === null) return "asc";
  if (current === "asc") return "desc";
  return null;
}

/**
 * Resolves a dot-separated key path on an object.
 * e.g. getNestedValue({ a: { b: 1 } }, "a.b") => 1
 */
function getNestedValue(obj: unknown, key: string): unknown {
  return key.split(".").reduce<unknown>((acc, part) => {
    if (acc != null && typeof acc === "object") {
      return (acc as Record<string, unknown>)[part];
    }
    return undefined;
  }, obj);
}

/**
 * Client-side sort for an array of objects.
 * Null/undefined values are always pushed to the end regardless of direction.
 */
export function sortData<T>(
  data: T[],
  key: string,
  direction: SortDirection
): T[] {
  if (!direction || !key) return data;

  return [...data].sort((a, b) => {
    const aVal = getNestedValue(a, key);
    const bVal = getNestedValue(b, key);

    // Nulls always to the end
    const aNull = aVal == null || aVal === "";
    const bNull = bVal == null || bVal === "";
    if (aNull && bNull) return 0;
    if (aNull) return 1;
    if (bNull) return -1;

    let comparison = 0;

    if (typeof aVal === "number" && typeof bVal === "number") {
      comparison = aVal - bVal;
    } else if (typeof aVal === "boolean" && typeof bVal === "boolean") {
      comparison = aVal === bVal ? 0 : aVal ? -1 : 1;
    } else {
      comparison = String(aVal).localeCompare(String(bVal), undefined, {
        numeric: true,
        sensitivity: "base",
      });
    }

    return direction === "asc" ? comparison : -comparison;
  });
}
