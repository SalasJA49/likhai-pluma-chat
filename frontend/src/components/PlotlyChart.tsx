import { useEffect, useState } from "react";

// Lazy-load Plotly core (plotly.js-dist-min) via the factory to ensure all trace types work (including scatter)
export default function PlotlyChart({ figure, title }: { figure: any; title?: string }) {
  const [Plot, setPlot] = useState<any>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [factoryMod, Plotly] = await Promise.all([
          import("react-plotly.js/factory"),
          import("plotly.js-dist-min"),
        ]);
        const createPlotlyComponent = (factoryMod as any).default || (factoryMod as any);
        const P = createPlotlyComponent((Plotly as any).default || Plotly);
        if (mounted) setPlot(() => P);
      } catch (e) {
        console.error("Failed to load Plotly", e);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  if (!figure) return null;
  if (!Plot) {
    return (
      <div className="w-full h-64 rounded-xl border bg-white flex items-center justify-center text-slate-500">
        Loading chart…
      </div>
    );
  }

  const data = Array.isArray(figure.data) ? figure.data : [];
  const layout = { ...figure.layout, title: title ?? figure.layout?.title };
  const config = { responsive: true, ...(figure.config || {}) } as any;

  return (
    <Plot
      data={data}
      layout={layout}
      config={config}
      useResizeHandler
      style={{ width: "100%", height: "100%" }}
    />
  );
}
