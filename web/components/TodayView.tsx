"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Game, Ratings, Team, useJson, useMeta, useTeams } from "@/lib/data";
import { useAsOf } from "@/lib/useAsOf";
import { dateIndex } from "@/lib/rankings";
import { addDays, fmt, pct, prettyDate, seasonOf, signed } from "@/lib/util";
import { shortConf } from "./RankingsView";
import TeamLogo from "./TeamLogo";

type Pre = { teams: string[]; off: (number | null)[]; def: (number | null)[] };

function WinBar({ p, lo, hi, a, h }: { p: number; lo: number | null; hi: number | null; a?: Team; h?: Team }) {
  const ca = a?.color ? `#${a.color}` : "#5b667a";
  const ch = h?.color ? `#${h.color}` : "#f2b544";
  return (
    <div className="w-full">
      <div className="relative h-2.5 overflow-hidden rounded-full bg-surface2">
        <div className="absolute inset-y-0 left-0" style={{ width: `${(1 - p) * 100}%`, background: ca, opacity: 0.85 }} />
        <div className="absolute inset-y-0 right-0" style={{ width: `${p * 100}%`, background: ch, opacity: 0.85 }} />
        {lo != null && hi != null && (
          <div className="absolute -inset-y-0.5 border-x-2 border-white/80" style={{ left: `${(1 - hi) * 100}%`, right: `${lo * 100}%`, background: "rgba(255,255,255,0.18)" }} title="80% interval on win probability" />
        )}
      </div>
    </div>
  );
}

function GameCard({ g, map, q }: { g: Game; map: Map<string, Team>; q?: number }) {
  const a = map.get(g.a), h = map.get(g.h);
  const nm = (t?: Team) => t?.short || t?.name || "TBD";
  const ph = g.p, pa = ph == null ? null : 1 - ph;
  const done = g.ok;
  const favH = (ph ?? 0.5) >= 0.5;
  return (
    <div className="card p-4">
      <div className="mb-3 flex items-center justify-between text-xs text-faint">
        <span>{g.n ? "Neutral site" : "Home: " + nm(h)}{g.note ? ` · ${g.note.replace("NCAA Men's Basketball Championship", "NCAA").slice(0, 40)}` : ""}</span>
        <span className="flex gap-2">
          {g.t !== "regular" && <span className="chip">{g.t.replace("_", " ")}</span>}
          {q != null && <span className="chip" title="Average AdjEM of the two teams">Quality {fmt(q, 0)}</span>}
        </span>
      </div>
      {[{ t: a, s: g.as, r: g.ar, pr: pa, sc: g.pa, id: g.a }, { t: h, s: g.hs, r: g.hr, pr: ph, sc: g.ph, id: g.h }].map((x, i) => {
        const won = done && x.s != null && (i === 0 ? (g.as as number) > (g.hs as number) : (g.hs as number) > (g.as as number));
        return (
          <div key={i} className="flex items-center gap-3 py-1">
            <TeamLogo team={x.t} size={30} />
            <Link href={`/team/${x.id}/`} className={`flex-1 truncate text-[15px] hover:text-accent ${done && !won ? "text-muted" : "font-medium"}`}>
              {x.r != null && <span className="mr-1.5 text-xs text-faint">{x.r}</span>}
              {x.t?.name ?? x.id}
            </Link>
            <span className="num w-14 text-right text-xs text-muted" title="Predicted score">{x.sc != null ? `~${x.sc.toFixed(0)}` : ""}</span>
            <span className="num w-12 text-right text-sm text-accent2">{x.pr != null ? pct(x.pr) : ""}</span>
            {done && <span className={`num w-10 text-right text-lg ${won ? "font-semibold" : "text-muted"}`}>{x.s}</span>}
          </div>
        );
      })}
      {ph != null && (
        <div className="mt-3">
          <WinBar p={ph} lo={g.plo} hi={g.phi} a={a} h={h} />
          <div className="mt-2 flex justify-between text-xs text-muted">
            <span>
              {nm(favH ? h : a)} by {fmt(Math.abs(g.pm ?? 0), 1)} · total {fmt((g.ph ?? 0) + (g.pa ?? 0), 0)}
            </span>
            {done && g.pm != null && (
              <span className={((g.hs as number) - (g.as as number)) - g.pm > 0 ? "text-accent2" : "text-[var(--bad)]"}>
                {nm(h)} vs exp {signed((g.hs as number) - (g.as as number) - g.pm, 1)}
              </span>
            )}
          </div>
        </div>
      )}
      {ph == null && <div className="mt-3 text-xs text-faint">No prediction (non-D-I opponent).</div>}
    </div>
  );
}

export default function TodayView() {
  const meta = useMeta();
  const { map } = useTeams();
  const { asof: auto, replay, offseason } = useAsOf(meta);
  const sp = useSearchParams();
  const router = useRouter();
  const day = sp.get("date") || auto || "";
  const season = day ? seasonOf(day) : 0;
  const { data: G } = useJson<{ games: Game[] }>(season && meta ? `games/${Math.min(season, meta.upcoming_season)}.json` : null);
  const ratingsPath = !meta || !season ? null : season <= meta.current_season ? `ratings/${season}.json` : "ratings/2027_preseason.json";
  const { data: RR } = useJson<Ratings & Pre>(ratingsPath);
  const [conf, setConf] = useState("All");

  const games = useMemo(() => (G?.games ?? []).filter((g) => g.d === day && g.t !== "exhibition"), [G, day]);
  const qual = useMemo(() => {
    const out = new Map<string, number>();
    if (!RR) return out;
    const isPre = !("dates" in RR && RR.dates);
    const i = isPre ? -1 : dateIndex(RR.dates, day);
    const m = new Map<string, number>();
    RR.teams.forEach((t, j) => {
      const o = isPre ? (RR.off as unknown as (number | null)[])[j] : i >= 0 ? RR.off[i][j] : null;
      const d = isPre ? (RR.def as unknown as (number | null)[])[j] : i >= 0 ? RR.def[i][j] : null;
      if (o != null && d != null) m.set(t, o - d);
    });
    games.forEach((g) => { const a = m.get(g.a), h = m.get(g.h); if (a != null && h != null) out.set(g.id, (a + h) / 2); });
    return out;
  }, [RR, games, day]);
  const confOf = (id: string) => shortConf(map.get(id)?.conf[String(season)] ?? map.get(id)?.conf[String(season - 1)]);
  const confs = useMemo(() => ["All", ...Array.from(new Set(games.flatMap((g) => [confOf(g.a), confOf(g.h)]))).filter(Boolean).sort()], [games, map]); // eslint-disable-line react-hooks/exhaustive-deps
  const shown = games.filter((g) => conf === "All" || confOf(g.a) === conf || confOf(g.h) === conf);
  const top = [...games].filter((g) => qual.has(g.id)).sort((a, b) => (qual.get(b.id) ?? 0) - (qual.get(a.id) ?? 0)).slice(0, 4);
  const list = [...shown].sort((a, b) => (qual.get(b.id) ?? -99) - (qual.get(a.id) ?? -99));

  const go = (d: string) => { const p = new URLSearchParams(sp.toString()); p.set("date", d); router.replace(`?${p}`, { scroll: false }); };
  const seasonEndDay = meta?.current_last_date;
  const nextGame = useMemo(() => (G?.games ?? []).find((g) => g.d > day)?.d, [G, day]);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold">{replay ? "Replay" : day === new Date().toISOString().slice(0, 10) ? "Today" : "Games"}: {day ? prettyDate(day) : "…"}</h1>
          <p className="mt-1 text-muted">Predicted score, win probability (bar shows the 80% interval) and result versus expectation for every game.</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="chip hover:text-ink" onClick={() => go(addDays(day, -1))}>← Prev</button>
          <input type="date" value={day} onChange={(e) => e.target.value && go(e.target.value)} aria-label="Date" />
          <button className="chip hover:text-ink" onClick={() => go(addDays(day, 1))}>Next →</button>
          <select value={conf} onChange={(e) => setConf(e.target.value)}>{confs.map((c) => <option key={c}>{c}</option>)}</select>
        </div>
      </div>
      {offseason && !sp.get("date") && (
        <div className="card mb-4 border-accent/40 px-4 py-3 text-[13px]">
          <span className="font-medium text-accent">Offseason.</span>{" "}
          <span className="text-muted">Showing the final day of the last completed season ({seasonEndDay ? prettyDate(seasonEndDay) : ""}). The 2026-27 season opens {meta ? prettyDate("2026-11-02") : ""}.</span>{" "}
          <button className="text-accent underline" onClick={() => go("2026-11-02")}>See opening-night predictions</button>
        </div>
      )}
      {top.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-medium uppercase tracking-wider text-muted">Top matchups (by average team rating)</h2>
          <div className="grid grid-cols-4 gap-3">
            {top.map((g) => (
              <div key={g.id} className="card flex items-center justify-between gap-2 px-3 py-2">
                <div className="flex items-center gap-1.5"><TeamLogo team={map.get(g.a)} size={26} /><span className="text-xs text-faint">@</span><TeamLogo team={map.get(g.h)} size={26} /></div>
                <div className="truncate text-right text-[13px]"><div>{map.get(g.a)?.abbr} @ {map.get(g.h)?.abbr}</div><div className="text-xs text-muted">{pct(g.p)} {map.get(g.h)?.abbr}</div></div>
              </div>
            ))}
          </div>
        </section>
      )}
      {!G ? (
        <div className="grid grid-cols-3 gap-4">{Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-44" />)}</div>
      ) : list.length === 0 ? (
        <div className="card p-10 text-center text-muted">
          No games on {prettyDate(day)}.{nextGame && <> Next scheduled day: <button className="text-accent underline" onClick={() => go(nextGame)}>{prettyDate(nextGame)}</button>.</>}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4 2xl:grid-cols-4">
          {list.map((g) => <GameCard key={g.id} g={g} map={map} q={qual.get(g.id)} />)}
        </div>
      )}
    </div>
  );
}
