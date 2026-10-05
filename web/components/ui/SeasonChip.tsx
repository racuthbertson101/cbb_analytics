import { seasonLabel } from "@/lib/format";

/** Season shown next to a page title, so every page says which season it describes. */
export default function SeasonChip({ season, note }: { season: number | null | undefined; note?: string }) {
  if (!season) return null;
  return (
    <span className="chip ml-3 align-middle font-sans font-normal" title="Season">
      {seasonLabel(season)}{note ? ` · ${note}` : ""}
    </span>
  );
}
