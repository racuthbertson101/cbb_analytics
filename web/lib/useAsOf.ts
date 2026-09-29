"use client";
import { useSearchParams } from "next/navigation";
import type { Meta } from "./data";

/** Resolves the effective "today": ?asof= (replay mode) > real date if inside the loaded season > last completed day. */
export function useAsOf(meta: Meta | null) {
  const sp = useSearchParams();
  const param = sp.get("asof");
  if (!meta) return { asof: null as string | null, replay: false, offseason: false };
  const today = new Date().toISOString().slice(0, 10);
  if (param && /^\d{4}-\d{2}-\d{2}$/.test(param)) return { asof: param, replay: true, offseason: false };
  const live = today <= meta.current_last_date && today >= meta.season_first_date;
  return live ? { asof: today, replay: false, offseason: false } : { asof: meta.default_asof, replay: false, offseason: true };
}
