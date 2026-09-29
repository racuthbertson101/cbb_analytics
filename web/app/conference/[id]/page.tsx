import fs from "node:fs";
import path from "node:path";
import { Suspense } from "react";
import ConferenceView from "@/components/ConferenceView";

export const dynamicParams = false;

export function generateStaticParams() {
  const p = path.join(process.cwd(), "public", "data", "tiebreakers.json");
  const rows: { id: string }[] = JSON.parse(fs.readFileSync(p, "utf8")).rows;
  return rows.filter((r) => r.id !== "_fallback").map((r) => ({ id: r.id }));
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <ConferenceView id={id} />
    </Suspense>
  );
}
