import { useState } from "react";

interface Option {
  id: string;
  name: string;
}

function summarise(options: Option[], selected: string[], placeholder: string) {
  const names = options.filter((o) => selected.includes(o.id)).map((o) => o.name);
  if (names.length === 0) return { text: placeholder, muted: true };
  if (names.length <= 2) return { text: names.join(", "), muted: false };
  return { text: `${names.length} categories selected`, muted: false };
}

export function CategoryMultiSelect({
  options,
  selected,
  onChange,
  placeholder = "Select categories",
}: {
  options: Option[];
  selected: string[];
  onChange: (ids: string[]) => void;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const summary = summarise(options, selected, placeholder);

  function toggle(id: string) {
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);
  }

  return (
    <div className="relative" onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-left"
      >
        <span className={`truncate ${summary.muted ? "text-slate-400" : "text-slate-700"}`}>{summary.text}</span>
        <span className={`text-slate-400 text-xs transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute left-0 right-0 top-full mt-1 z-20 bg-white border border-slate-200 rounded-lg shadow-lg max-h-56 overflow-y-auto py-1">
            {options.length === 0 && <div className="px-3 py-2 text-sm text-slate-400">No categories available</div>}
            {options.map((o) => (
              <label
                key={o.id}
                className="flex items-center gap-2.5 px-3 py-2 text-sm text-slate-700 hover:bg-brand-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(o.id)}
                  onChange={() => toggle(o.id)}
                  className="h-4 w-4 rounded border-slate-300 accent-brand-500"
                />
                {o.name}
              </label>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
