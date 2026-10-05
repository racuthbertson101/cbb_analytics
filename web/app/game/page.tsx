import { Suspense } from "react";
import GameView from "@/components/GameView";

export default function Page() {
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <GameView />
    </Suspense>
  );
}
