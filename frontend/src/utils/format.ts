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

