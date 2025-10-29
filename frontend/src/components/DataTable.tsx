type Props = { title?: string; columns: string[]; rows: Array<Record<string, any>> };

export default function DataTable({ title, columns, rows }: Props) {
  if (!columns?.length || !rows?.length) return null;
  return (
    <div>
      {title && <h4 className="font-medium mb-2">{title}</h4>}
      <div className="overflow-auto border rounded-xl">
        <table className="min-w-[640px] w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              {columns.map((c) => (
                <th key={c} className="text-left p-2">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => (
              <tr key={idx} className="odd:bg-white even:bg-slate-50/40">
                {columns.map((c) => (
                  <td key={c} className="p-2 border-t">
                    {fmt(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function fmt(v: any) {
  if (typeof v === "number" && isFinite(v)) {
    // prettier numeric display
    const abs = Math.abs(v);
    if (abs >= 1_000_000) return (v / 1_000_000).toFixed(2) + "M";
    if (abs >= 1_000) return (v / 1_000).toFixed(2) + "k";
    return v.toFixed(2);
  }
  return v ?? "";
}
