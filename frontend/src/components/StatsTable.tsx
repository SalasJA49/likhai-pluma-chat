export default function StatsTable({ statistics }: { statistics: Record<string, any> }) {
  if (!statistics || Object.keys(statistics).length === 0) return null;

  const cols = Object.keys(statistics);

  return (
    <div className="space-y-6">
      <div>
        <h4 className="font-medium mb-2">Descriptive Statistics</h4>
        <div className="overflow-auto border rounded-xl">
          <table className="min-w-[640px] w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left p-2">Column</th>
                <th className="text-right p-2">Count</th>
                <th className="text-right p-2">Missing</th>
                <th className="text-right p-2">Mean</th>
                <th className="text-right p-2">Median</th>
                <th className="text-right p-2">Std</th>
                <th className="text-right p-2">Min</th>
                <th className="text-right p-2">Q1</th>
                <th className="text-right p-2">Q3</th>
                <th className="text-right p-2">Max</th>
              </tr>
            </thead>
            <tbody>
              {cols.map((c) => {
                const s = statistics[c] || {};
                return (
                  <tr key={c} className="odd:bg-white even:bg-slate-50/40">
                    <td className="p-2 font-medium text-slate-700">{c}</td>
                    <td className="p-2 text-right">{s.count ?? 0}</td>
                    <td className="p-2 text-right">{s.missing ?? 0}</td>
                    <td className="p-2 text-right">{fmt(s.mean)}</td>
                    <td className="p-2 text-right">{fmt(s.median)}</td>
                    <td className="p-2 text-right">{fmt(s.std)}</td>
                    <td className="p-2 text-right">{fmt(s.min)}</td>
                    <td className="p-2 text-right">{fmt(s.q25)}</td>
                    <td className="p-2 text-right">{fmt(s.q75)}</td>
                    <td className="p-2 text-right">{fmt(s.max)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h4 className="font-medium mb-2">Distribution Metrics</h4>
        <div className="overflow-auto border rounded-xl">
          <table className="min-w-[480px] w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left p-2">Column</th>
                <th className="text-right p-2">Range</th>
                <th className="text-right p-2">IQR</th>
                <th className="text-right p-2">CV (%)</th>
                <th className="text-right p-2">Skewness</th>
              </tr>
            </thead>
            <tbody>
              {cols.map((c) => {
                const s = statistics[c] || {};
                const skew = typeof s.skewness === "number" ? `${s.skewness.toFixed(2)}` : "";
                return (
                  <tr key={c} className="odd:bg-white even:bg-slate-50/40">
                    <td className="p-2 font-medium text-slate-700">{c}</td>
                    <td className="p-2 text-right">{fmt(s.range)}</td>
                    <td className="p-2 text-right">{fmt(s.iqr)}</td>
                    <td className="p-2 text-right">{fmt(s.cv)}</td>
                    <td className="p-2 text-right">{skew}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="text-xs text-slate-500 mt-2">
          Q1/Q3 = 25th/75th percentiles • IQR = Q3 − Q1 • CV = Std/Mean × 100
        </div>
      </div>
    </div>
  );
}

function fmt(v: any) {
  return typeof v === "number" && isFinite(v) ? v.toFixed(2) : v ?? "";
}
