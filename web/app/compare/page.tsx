import { Suspense } from "react";
import CompareView from "@/components/CompareView";

export default function Page() {
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <CompareView />
    </Suspense>
  );
}
