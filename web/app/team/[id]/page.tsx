import fs from "node:fs";
import path from "node:path";
import { Suspense } from "react";
import TeamView from "@/components/TeamView";

export const dynamicParams = false;

export function generateStaticParams() {
  const p = path.join(process.cwd(), "public", "data", "teams.json");
  const teams: { id: string }[] = JSON.parse(fs.readFileSync(p, "utf8")).teams;
  return teams.map((t) => ({ id: t.id }));
}

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <TeamView id={id} />
    </Suspense>
  );
}
