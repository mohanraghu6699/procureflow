export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 border-t border-slate-100 text-sm text-slate-500">
      <div>
        Showing <span className="font-medium text-slate-700">{from}</span>-
        <span className="font-medium text-slate-700">{to}</span> of{" "}
        <span className="font-medium text-slate-700">{total}</span>
      </div>
      <div className="flex items-center gap-2">
        <button
          className="px-3 py-1.5 rounded-md border border-slate-200 disabled:opacity-40 hover:bg-slate-100 transition-colors"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </button>
        <span className="text-slate-600">
          Page {page} of {totalPages}
        </span>
        <button
          className="px-3 py-1.5 rounded-md border border-slate-200 disabled:opacity-40 hover:bg-slate-100 transition-colors"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
