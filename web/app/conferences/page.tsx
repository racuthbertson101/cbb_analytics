import { Suspense } from "react";
import ConferencesView from "@/components/ConferencesView";

export default function Page() {
  return (
    <Suspense fallback={<div className="skeleton h-96 w-full" />}>
      <ConferencesView />
    </Suspense>
  );
}
