import Link from "next/link";

/** Every rendered score or matchup row links to its Game page (IMPROVEMENT_PLAN 4.2 linking rule). */
export const gameHref = (id: string, season: number) => `/game/?id=${id}&season=${season}`;

export default function GameLink({ id, season, children, className = "" }: { id: string; season: number; children: React.ReactNode; className?: string }) {
  return (
    <Link href={gameHref(id, season)} className={`hover:text-accent hover:underline ${className}`}>
      {children}
    </Link>
  );
}

/** A score inside a game link; `.score` is what the Playwright linking check looks for. */
export function ScoreLink({ id, season, children, className = "" }: { id: string; season: number; children: React.ReactNode; className?: string }) {
  return (
    <GameLink id={id} season={season} className={className}>
      <span className="score">{children}</span>
    </GameLink>
  );
}
