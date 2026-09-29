"use client";
import { useState } from "react";
import type { Team } from "@/lib/data";

export default function TeamLogo({ team, size = 24 }: { team?: Team | null; size?: number }) {
  const [bad, setBad] = useState(false);
  const color = team?.color ? `#${team.color}` : "#39445a";
  if (!team || !team.logo || bad) {
    const letters = (team?.abbr || team?.short || "?").slice(0, 3).toUpperCase();
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
        style={{ width: size, height: size, background: color, fontSize: Math.max(8, size * 0.36) }}
        aria-hidden
      >
        {letters}
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={team.logo} alt="" width={size} height={size} loading="lazy" onError={() => setBad(true)} className="shrink-0 object-contain" style={{ width: size, height: size }} />;
}
