import { Suspense } from "react";
import PredictionsView from "@/components/PredictionsView";

export default function Page() {
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <PredictionsView />
    </Suspense>
  );
}
