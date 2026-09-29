import { Suspense } from "react";
import PlayersView from "@/components/PlayersView";

export default function Page() {
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <PlayersView />
    </Suspense>
  );
}
