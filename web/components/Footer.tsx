"use client";
import { useEffect, useState } from "react";
import { useJson } from "@/lib/data";
import { prettyDate, seasonLabel } from "@/lib/util";

type Status = { data_through: string | null; season: number; updated: string; live?: boolean; source: string };

/** DEFINITION: during the season (Nov 1 - Apr 15) data older than this many hours is flagged as stale. */
const STALE_HOURS = 36;
const inSeasonWindow = (d: Date) => {
  const m = d.getUTCMonth() + 1, day = d.getUTCDate();
  return m >= 11 || m <= 3 || (m === 4 && day <= 15);
};

export default function Footer() {
  const { data: st } = useJson<Status>("status.json");
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);
  const updated = st ? new Date(st.updated) : null;
  const hours = updated && now ? (now.getTime() - updated.getTime()) / 36e5 : 0;
  const stale = !!now && inSeasonWindow(now) && hours > STALE_HOURS;
  const updatedText = updated?.toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York", timeZoneName: "short" });
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-[1680px] flex-wrap items-center gap-x-6 gap-y-1 px-6 py-4 text-xs text-faint">
        <span>Men&apos;s Division I basketball</span>
        {st && (
          <span data-testid="freshness" className={stale ? "text-accent" : undefined} title={stale ? `Not updated for ${Math.round(hours)} hours during the season` : undefined}>
            {stale && "⚠ "}
            {st.data_through ? `Data through ${prettyDate(st.data_through)} (${seasonLabel(st.season)})` : `No ${seasonLabel(st.season)} games yet`}
            {" · "}updated {updatedText}
          </span>
        )}
      </div>
    </footer>
  );
}
