/** Marks how a number relates to the model: "in the prediction", "context only" (not used by the model) or "experimental". */
const STYLE = {
  model: { label: "in the prediction", title: "This input is part of the model's prediction." },
  context: { label: "context only", title: "Shown for context; not used by the prediction (no validated effect)." },
  experimental: { label: "experimental", title: "Experimental measure with known biases; see Methodology." },
} as const;

export default function ContextTag({ kind, title }: { kind: keyof typeof STYLE; title?: string }) {
  const s = STYLE[kind];
  return (
    <span className="chip ml-2 align-middle text-[10.5px] normal-case tracking-normal" title={title ?? s.title}>
      {s.label}
    </span>
  );
}
