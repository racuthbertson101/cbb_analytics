"use client";
import { useMemo } from "react";
import { useJson } from "./data";

export type P = Record<string, number | string | null> & { id: string; name: string; tid: string };
type Shard = { season: number; ref_min: number; cols: string[]; rows: (number | string | null)[][] };

export function usePlayers(season: number | null) {
  const { data } = useJson<Shard>(season ? `players/${season}.json` : null);
  return useMemo(() => {
    if (!data) return null;
    return { refMin: data.ref_min, rows: data.rows.map((r) => Object.fromEntries(data.cols.map((c, i) => [c, r[i]])) as P) };
  }, [data]);
}
