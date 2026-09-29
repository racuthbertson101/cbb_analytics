"use client";
import { useEffect, useState } from "react";

export const BASE = process.env.NEXT_PUBLIC_BASE_PATH || "";
export const dataUrl = (p: string) => `${BASE}/data/${p.replace(/^\//, "")}`;
export const href = (p: string) => `${BASE}${p}`;

const cache = new Map<string, Promise<unknown>>();
export function loadJson<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    cache.set(
      path,
      fetch(dataUrl(path)).then((r) => {
        if (!r.ok) throw new Error(`${path}: ${r.status}`);
        return r.json();
      }),
    );
  }
  return cache.get(path) as Promise<T>;
}

export function useJson<T>(path: string | null): { data: T | null; error: string | null } {
  const [state, set] = useState<{ path: string | null; data: T | null; error: string | null }>({ path: null, data: null, error: null });
  useEffect(() => {
    if (!path) return;
    let live = true;
    loadJson<T>(path)
      .then((d) => live && set({ path, data: d, error: null }))
      .catch((e) => live && set({ path, data: null, error: String(e) }));
    return () => {
      live = false;
    };
  }, [path]);
  if (state.path !== path) return { data: null, error: null };
  return { data: state.data, error: state.error };
}

export type Team = { id: string; name: string; short: string; abbr: string; loc: string; color: string; alt: string; logo: string; conf: Record<string, string> };
export type Meta = { version: number; current_season: number; upcoming_season: number | null; upcoming_first_date: string | null; seasons: number[]; last_game_date: string; default_asof: string; current_last_date: string; season_first_date: string; generated: string };
export type Game = {
  id: string; d: string; a: string; h: string; as: number | null; hs: number | null; n: boolean; t: string; cg: boolean; ok: boolean;
  pm: number | null; pp: number | null; p: number | null; plo: number | null; phi: number | null; ph: number | null; pa: number | null;
  ar: number | null; hr: number | null; d1: boolean; note: string | null; w: number | null; wc: (number | null)[] | null;
};
export type Ratings = { season: number; dates: string[]; teams: string[]; off: (number | null)[][]; def: (number | null)[][]; tempo: (number | null)[][]; gp: (number | null)[][] };

export function useTeams() {
  const { data } = useJson<{ teams: Team[] }>("teams.json");
  const map = new Map<string, Team>();
  data?.teams.forEach((t) => map.set(t.id, t));
  return { teams: data?.teams ?? null, map };
}
export const useMeta = () => useJson<Meta>("meta.json").data;
