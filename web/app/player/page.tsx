import { Suspense } from "react";
import PlayerView from "@/components/PlayerView";

export default function Page() {
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <PlayerView />
    </Suspense>
  );
}
