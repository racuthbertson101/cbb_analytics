import { Suspense } from "react";
import RankingsView from "@/components/RankingsView";

export default function Page() {
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <RankingsView />
    </Suspense>
  );
}
