"use client";

import { useState, useMemo, useCallback } from "react";
import { SortState, SortDirection, nextSortDirection, sortData } from "@/lib/sort";

export function useSort<T>(data: T[]) {
  const [sort, setSort] = useState<SortState>({ key: "", direction: null });

  const handleSort = useCallback((key: string) => {
    setSort((prev) => {
      if (prev.key !== key) {
        return { key, direction: "asc" };
      }
      const next = nextSortDirection(prev.direction);
      return { key: next === null ? "" : key, direction: next };
    });
  }, []);

  const sortedData = useMemo(
    () => sortData(data, sort.key, sort.direction),
    [data, sort.key, sort.direction]
  );

  return { sort, handleSort, sortedData } as const;
}
