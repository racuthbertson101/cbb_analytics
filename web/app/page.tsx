import { Suspense } from "react";
import TodayView from "@/components/TodayView";

export default function Page() {
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <TodayView />
    </Suspense>
  );
}
