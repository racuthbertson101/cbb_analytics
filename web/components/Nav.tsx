"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense } from "react";
import SearchPalette from "./SearchPalette";
import site from "@/config/site.json";

const items = site.nav as [string, string][];

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
        <div className="ml-auto flex items-center gap-3"><SearchPalette /><span className="text-xs text-faint">Men&apos;s Division I</span></div>
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
