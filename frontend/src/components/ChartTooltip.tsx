// Recharts clones the element passed as a tooltip's `content` and injects these props.
interface TooltipRow {
  name?: string | number;
  value?: string | number;
  color?: string;
  fill?: string;
  dataKey?: string | number;
}

interface TooltipProps {
  active?: boolean;
  payload?: readonly TooltipRow[];
  label?: string | number;
}

function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="min-w-[8.5rem] rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      {title && <div className="mb-1.5 font-semibold text-slate-800">{title}</div>}
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function Row({ color, name, value }: { color?: string; name: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-slate-500">{name}</span>
      <span className="ml-auto pl-4 font-semibold tabular-nums text-slate-900">{value}</span>
    </div>
  );
}

/** Bar-chart tooltip: the category as a title, then one coloured row per series in the order given. */
export function ChartTooltip({
  active,
  payload,
  label,
  order = [],
}: TooltipProps & { order?: string[] }) {
  if (!active || !payload || payload.length === 0) return null;
  const rank = (row: TooltipRow) => {
    const i = order.indexOf(String(row.dataKey));
    return i === -1 ? order.length : i;
  };
  const rows = [...payload].sort((a, b) => rank(a) - rank(b));
  return (
    <Card title={label === undefined ? undefined : String(label)}>
      {rows.map((row) => (
        <Row key={String(row.dataKey ?? row.name)} color={row.color ?? row.fill} name={String(row.name ?? "")} value={String(row.value ?? "")} />
      ))}
    </Card>
  );
}
