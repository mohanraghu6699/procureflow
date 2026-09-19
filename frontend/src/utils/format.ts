const amountFormatter = new Intl.NumberFormat("en-AE", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatCurrency(amount: string | number): string {
  return amountFormatter.format(Number(amount));
}

// Today (or any date) as YYYY-MM-DD in the viewer's local timezone.
export function localDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

// Whole calendar days from `from` to `to` (positive when `to` is later). Takes ISO strings or YYYY-MM-DD.
export function daysBetween(from: string, to: string): number {
  const utc = (s: string) => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10));
  return Math.round((utc(to) - utc(from)) / 86400000);
}

const plural = (n: number) => `${n} day${n === 1 ? "" : "s"}`;

export interface DueInfo {
  label: string;
  tone: "good" | "bad" | "warn" | "neutral";
}

// How a delivery date compares with the required-by date.
export function deliveryTiming(deliveryDate: string, requiredDate: string): DueInfo {
  const late = daysBetween(requiredDate, deliveryDate);
  return late > 0 ? { label: `${plural(late)} late`, tone: "bad" } : { label: "On time", tone: "good" };
}

// Where an open order stands against its required-by date.
export function openOrderDue(requiredDate: string): DueInfo {
  const remaining = daysBetween(localDate(new Date()), requiredDate);
  if (remaining < 0) return { label: `Overdue by ${plural(-remaining)}`, tone: "bad" };
  if (remaining === 0) return { label: "Due today", tone: "warn" };
  return { label: `Due in ${plural(remaining)}`, tone: "neutral" };
}


export interface TrendInfo {
  text: string;
  tone: "up" | "down" | "flat";
}

// Period-over-period change for a dashboard card, e.g. "+12% vs last month". With nothing to compare
// against (previous = 0) it falls back to a plain count so a new system doesn't show "Infinity%".
export function describeTrend(
  point: { current: string | number; previous: string | number },
  period: "month" | "week",
  noun: string,
  money = false
): TrendInfo {
  const current = Number(point.current);
  const previous = Number(point.previous);
  const shown = money ? formatCurrency(current) : String(current);

  if (previous === 0 && current === 0) return { text: `Nothing ${noun} this ${period}`, tone: "flat" };
  if (previous === 0) return { text: `${shown} ${noun} this ${period}`, tone: "up" };

  const pct = Math.round(((current - previous) / previous) * 100);
  if (pct === 0) return { text: `0% vs last ${period}`, tone: "flat" };
  return { text: `${pct > 0 ? "+" : ""}${pct}% vs last ${period}`, tone: pct > 0 ? "up" : "down" };
}
