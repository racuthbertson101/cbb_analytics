"use client";
import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Ratings, useJson, useMeta, useTeams } from "@/lib/data";
import { fmt, pct, seasonLabel, signed } from "@/lib/util";
import { cdf, interp, Pred } from "@/lib/predict";
import TeamLogo from "./TeamLogo";
import SeasonChip from "./ui/SeasonChip";

type Pre = { teams: string[]; off: (number | null)[]; def: (number | null)[]; tempo: (number | null)[]; mu: number; hca: number };
export default function CompareView() {
  const meta = useMeta();
  const { teams, map } = useTeams();
  const sp = useSearchParams();
  const router = useRouter();
  const season = Number(sp.get("season")) || meta?.current_season || 0;
  const upcoming = !!meta && meta.upcoming_season != null && season === meta.upcoming_season;
  const a = sp.get("a") || "130", b = sp.get("b") || "150", site = Number(sp.get("site") ?? "0");
  const { data: R } = useJson<Ratings & { mu: number[]; hca: number[] }>(meta && season && !upcoming ? `ratings/${season}.json` : null);
  const { data: PRE } = useJson<Pre>(upcoming ? `ratings/${season}_preseason.json` : null);
  const { data: PP } = useJson<Pred>("params/predict.json");
  const set = (k: string, v: string) => { const p = new URLSearchParams(sp.toString()); p.set(k, v); router.replace(`?${p}`, { scroll: false }); };

  const out = useMemo(() => {
    if (!PP) return null;
    let t: string[], off: (number | null)[], def: (number | null)[], tempo: (number | null)[], mu: number, hca: number;
    if (R) { const i = R.dates.length - 1; t = R.teams; off = R.off[i]; def = R.def[i]; tempo = R.tempo[i]; mu = R.mu[i]; hca = R.hca[i]; }
    else if (PRE) { t = PRE.teams; off = PRE.off; def = PRE.def; tempo = PRE.tempo; mu = PRE.mu; hca = PRE.hca; }
    else return null;
    const i = t.indexOf(a), j = t.indexOf(b);
    if (i < 0 || j < 0 || off[i] == null || off[j] == null) return { missing: true as const };
    const adv = hca * site; // site: +1 = A at home, 0 neutral, -1 = A away
    const ea = (off[i] as number) + (def[j] as number) - mu + adv, eb = (off[j] as number) + (def[i] as number) - mu - adv;
    const poss = (((tempo[i] as number) + (tempo[j] as number)) / 2);
    const m = ((ea - eb) * poss) / 100;
    const prob = (mm: number) => interp(cdf(mm / Math.max(PP.sigma_coef[0] + PP.sigma_coef[1] * (poss - 68), 3)), PP.cal_x, PP.cal_y);
    return { missing: false as const, ea, eb, poss, m, sa: (ea * poss) / 100, sb: (eb * poss) / 100, p: prob(m), mlo: m + PP.q10, mhi: m + PP.q90, off, def, i, j };
  }, [R, PRE, PP, a, b, site]);

  const sorted = useMemo(() => [...(teams ?? [])].sort((x, y) => x.name.localeCompare(y.name)), [teams]);
  const ta = map.get(a), tb = map.get(b);
  const seasons = [...(meta?.seasons ?? []), ...(meta?.upcoming_season ? [meta.upcoming_season] : [])].reverse();

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-3xl font-semibold">Compare<SeasonChip season={season} note={upcoming ? "preseason" : undefined} /></h1>
      <p className="mb-6 mt-1 text-muted">Pick any two teams and a site to get the model&apos;s prediction using ratings at the end of the chosen season (or the preseason projection).</p>
      <div className="card mb-6 grid grid-cols-[1fr_auto_1fr] items-end gap-4 p-5">
        {[["a", a, ta], ["b", b, tb]].map(([k, v, t], idx) => (
          <div key={k as string} className={idx === 1 ? "col-start-3" : ""}>
            <div className="mb-2 flex items-center gap-3"><TeamLogo team={t as never} size={44} /><span className="text-lg font-medium">{(t as { name?: string })?.name}</span></div>
            <select className="w-full" value={v as string} onChange={(e) => set(k as string, e.target.value)}>{sorted.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
          </div>
        ))}
        <div className="col-start-2 row-start-1 self-center pb-6 text-faint">vs</div>
        <div className="col-span-3 flex flex-wrap items-center gap-3">
          <span className="text-xs uppercase tracking-wider text-muted">Site</span>
          {[[1, `${ta?.short ?? "A"} home`], [0, "Neutral"], [-1, `${tb?.short ?? "B"} home`]].map(([v, l]) => (
            <button key={String(v)} onClick={() => set("site", String(v))} className={`chip ${site === v ? "!border-accent !text-accent" : ""}`}>{l}</button>
          ))}
          <select value={season} onChange={(e) => set("season", e.target.value)} className="ml-auto">
            {seasons.map((s) => <option key={s} value={s}>{seasonLabel(s)}{s === meta?.upcoming_season ? " (preseason)" : " (final)"}</option>)}
          </select>
        </div>
      </div>
      {!out ? <div className="skeleton h-56" /> : out.missing ? (
        <div className="card p-8 text-center text-muted">One of these teams has no rating in {seasonLabel(season)}. Choose another season.</div>
      ) : (
        <div className="card p-6">
          <div className="mb-4 grid grid-cols-3 items-center text-center">
            <div><div className="num text-5xl font-semibold">{fmt(out.sa, 0)}</div><div className="mt-1 text-sm text-muted">{ta?.short}</div></div>
            <div><div className="text-xs uppercase tracking-wider text-muted">Predicted score</div><div className="num mt-1 text-lg">{fmt(out.poss, 0)} possessions</div></div>
            <div><div className="num text-5xl font-semibold">{fmt(out.sb, 0)}</div><div className="mt-1 text-sm text-muted">{tb?.short}</div></div>
          </div>
          <div className="relative h-4 overflow-hidden rounded-full bg-surface2">
            <div className="absolute inset-y-0 left-0" style={{ width: `${out.p * 100}%`, background: ta?.color ? `#${ta.color}` : "#f2b544", opacity: 0.85 }} />
            <div className="absolute inset-y-0 right-0" style={{ width: `${(1 - out.p) * 100}%`, background: tb?.color ? `#${tb.color}` : "#4cc9c0", opacity: 0.6 }} />
          </div>
          <div className="mt-2 flex justify-between text-lg"><span className="num text-accent">{pct(out.p, 1)}</span><span className="num text-muted">{pct(1 - out.p, 1)}</span></div>
          <div className="mt-4 grid grid-cols-3 gap-4 text-center text-sm">
            <div className="card p-3"><div className="text-xs text-muted">Margin</div><div className="num text-lg">{ta?.short} {signed(out.m, 1)}</div></div>
            <div className="card p-3"><div className="text-xs text-muted" title="Outcome interval from historical prediction errors: 80% of actual margins land in this range">80% of results land in</div><div className="num text-lg">{ta?.short} {signed(out.mlo, 0)} to {signed(out.mhi, 0)}</div></div>
            <div className="card p-3"><div className="text-xs text-muted">Total</div><div className="num text-lg">{fmt(out.sa + out.sb, 0)}</div></div>
          </div>
          <p className="mt-4 text-xs text-faint">Uses adjusted offense/defense/tempo, the fitted home-court advantage, the tempo-dependent spread and the calibrated win probability from the Methodology page.</p>
        </div>
      )}
    </div>
  );
}
