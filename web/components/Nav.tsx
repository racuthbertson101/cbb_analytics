"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";

const items = [
  ["/", "Today"],
  ["/rankings/", "Rankings"],
  ["/tournament/", "Tournament"],
  ["/methodology/", "Methodology"],
];

function Inner() {
  const path = usePathname() || "/";
  const active = (h: string) => (h === "/" ? path === "/" : path.startsWith(h.replace(/\/$/, "")));
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur">
      <div className="mx-auto flex max-w-[1680px] items-center gap-8 px-6 py-3">
        <Link href="/" className="display flex items-baseline gap-2 text-lg font-semibold">
          <span className="inline-block h-3 w-3 rounded-full bg-accent" />
          CBB<span className="text-accent">Analytics</span>
        </Link>
        <nav className="flex gap-1">
          {items.map(([h, l]) => (
            <Link key={h} href={h} className={`rounded-md px-3 py-1.5 text-[13px] transition-colors ${active(h) ? "bg-surface2 text-ink" : "text-muted hover:text-ink"}`}>
              {l}
            </Link>
          ))}
        </nav>
        <div className="ml-auto text-xs text-faint">Men&apos;s Division I</div>
      </div>
    </header>
  );
}
export default function Nav() {
  return (
    <Suspense fallback={null}>
      <Inner />
    </Suspense>
  );
}
