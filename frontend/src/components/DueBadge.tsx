import type { DueInfo } from "../utils/format";

const TONE_CLASSES: Record<DueInfo["tone"], string> = {
  good: "bg-emerald-100 text-emerald-700",
  bad: "bg-red-100 text-red-700",
  warn: "bg-amber-100 text-amber-700",
  neutral: "bg-slate-100 text-slate-600",
};

export function DueBadge({ info }: { info: DueInfo }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${TONE_CLASSES[info.tone]}`}>
      {info.label}
    </span>
  );
}
