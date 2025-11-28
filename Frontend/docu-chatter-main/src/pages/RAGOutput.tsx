import React, { useState } from "react";
import { useNavigate, useLocation, useParams, Outlet } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ArrowLeft, Download, FileText } from "lucide-react";
import { useChatbots } from "@/hooks/useChatbots";
import { useToast } from "@/hooks/use-toast";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from "recharts";
import { saveAs } from "file-saver";

/* --------------------------------------------------------
   FIX: CustomTooltip MUST be OUTSIDE component
   -------------------------------------------------------- */
const CustomTooltip = ({ active, payload, hoveredLabel }: any) => {
  if (!active || !payload || !payload.length) return null;

  const shown = hoveredLabel
    ? payload.filter((p: any) => p.name === hoveredLabel)
    : payload;

  const toShow = shown.length ? shown : [payload[0]];

  return (
    <div className="bg-white p-2 rounded shadow border border-gray-200 text-sm">
      {toShow.map((item: any) => (
        <div key={item.name}>
          <strong>{item.name}</strong>: {item.value}
        </div>
      ))}
    </div>
  );
};

/* --------------------------------------------------------
   UI Color Palette
   -------------------------------------------------------- */
const PALETTE = [
  "#4F46E5",
  "#7C3AED",
  "#DB2777",
  "#F59E0B",
  "#10B981",
  "#EF4444",
];

type Counts = Record<string, number>;

const RAGOutput: React.FC = () => {
  /* --------------------------------------------------------
     HOOKS — always first, always same order, FIXED ✓
     -------------------------------------------------------- */
  const navigate = useNavigate();
  const { toast } = useToast();
  const { id } = useParams();
  const { getChatbot } = useChatbots();
  const location = useLocation();
  const chatbot = id ? getChatbot(id as string) : null;
  const apiResponse = (location.state as any)?.evaluationResponse;
  const [hoveredLabel, setHoveredLabel] = useState<string | null>(null);

  /* --------------------------------------------------------
     MANDATORY early returns — AFTER hooks (safe) ✓
     -------------------------------------------------------- */
  if (!chatbot)
    return (
      <div className="p-20 text-center">
        <h1>Chatbot Not Found</h1>
      </div>
    );

  if (!apiResponse)
    return (
      <div className="p-20 text-center">
        <h1>No Data</h1>
      </div>
    );

  /* --------------------------------------------------------
     PURE VALUES (NO HOOKS) — ⭐ FIX FOR ERROR ⭐
     -------------------------------------------------------- */
  const metrics: string[] =
    apiResponse.metrics || Object.keys(apiResponse.results || {});

  const normalize = (v: any) =>
    v && String(v).toLowerCase() !== "unknown" ? v : null;

  /* --------------------------------------------------------
     Compute per-metric counts (NO useMemo, pure code)
     -------------------------------------------------------- */
  const perMetricCounts: Record<string, Counts> = {};
  const labelSet = new Set<string>();

  for (const metric of metrics) {
    const results = apiResponse.results[metric]?.results || [];
    const counts: Counts = {};

    for (const r of results) {
      for (const k of Object.keys(r)) {
        if (k.endsWith("_eval")) {
          const val = normalize(r[k]);
          if (val) {
            counts[val] = (counts[val] || 0) + 1;
            labelSet.add(val);
          }
        }
      }
    }

    perMetricCounts[metric] = counts;
  }

  const allLabels = Array.from(labelSet);

  /* --------------------------------------------------------
     Label colors
     -------------------------------------------------------- */
  const labelColorMap: Record<string, string> = {};
  allLabels.forEach((label, i) => {
    labelColorMap[label] = PALETTE[i % PALETTE.length];
  });

  /* --------------------------------------------------------
     Overall stacked bar data
     -------------------------------------------------------- */
  const overallBarData = metrics.map((metric) => {
    const counts = perMetricCounts[metric];
    const row: any = { name: metric };

    for (const lbl of allLabels) {
      row[lbl] = counts[lbl] || 0;
    }
    return row;
  });

  /* --------------------------------------------------------
     Global summary
     -------------------------------------------------------- */
  const globalCounts: Counts = {};
  let totalRecords = 0;

  for (const metric of metrics) {
    const metricData = apiResponse.results[metric];
    totalRecords += metricData?.total_records || metricData?.results?.length || 0;

    const counts = perMetricCounts[metric];
    for (const [lbl, val] of Object.entries(counts)) {
      globalCounts[lbl] = (globalCounts[lbl] || 0) + val;
    }
  }

  const totalLabels = Object.values(globalCounts).reduce((a, b) => a + b, 0);
  const mostCommon =
    Object.entries(globalCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || "N/A";

  const factualRate = totalLabels
    ? (((globalCounts["factual"] || 0) / totalLabels) * 100).toFixed(1)
    : "0";
  /* --------------------------------------------------------
     EXCEL/CSV EXPORTS
     -------------------------------------------------------- */
  const exportJSON = () => {
    saveAs(
      new Blob(
        [JSON.stringify({ meta: apiResponse, results: apiResponse.results }, null, 2)],
        { type: "application/json" }
      ),
      `${chatbot.name}_evaluation.json`
    );
    toast({ title: "JSON exported!" });
  };

  const exportCSV = () => {
    const rows: string[] = [];
    const header = ["metric", "label", "value"];
    rows.push(header.join(","));

    for (const metric of metrics) {
      const counts = perMetricCounts[metric];
      for (const [lbl, val] of Object.entries(counts)) {
        rows.push([metric, lbl, String(val)].join(","));
      }
    }

    saveAs(
      new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" }),
      `${chatbot.name}_evaluation.csv`
    );
    toast({ title: "CSV exported!" });
  };

  /* --------------------------------------------------------
     RENDER
     -------------------------------------------------------- */
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">

      {/* HEADER */}
      <header className="bg-white border-b border-slate-200 p-4 flex items-center gap-4 sticky top-0 z-30">
        <Button variant="ghost" onClick={() => navigate(`/evaluation-selection/${id}`)}>
          <ArrowLeft />
        </Button>
        <h1 className="text-2xl font-semibold">{chatbot.name} – Evaluation</h1>
      </header>

      <main className="max-w-7xl mx-auto p-6 space-y-10">

        {/* EXPORT BUTTONS */}
        <div className="flex justify-end gap-4">
          <Button onClick={exportCSV} className="bg-indigo-600 text-white">
            <Download className="w-4 h-4" /> CSV
          </Button>
          <Button onClick={exportJSON} className="bg-emerald-600 text-white">
            <FileText className="w-4 h-4" /> JSON
          </Button>
        </div>

        {/* =====================================================
             OVERALL SUMMARY (left) + STACKED BAR (right)
           ===================================================== */}
        <Card>
          <CardHeader>
            <CardTitle>Overall Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col lg:flex-row gap-6">

              {/* LEFT: SUMMARY */}
              <div className="lg:w-1/2 p-4 bg-white border rounded-md">
                <p>Total Metrics: <strong>{metrics.length}</strong></p>
                <p>Total Records: <strong>{totalRecords}</strong></p>

                <p className="mt-3 font-medium">Outcome Distribution:</p>
                <ul className="ml-6 list-disc">
                  {Object.entries(globalCounts).map(([lbl, val]) => (
                    <li key={lbl}>
                      <span
                        className="inline-block w-3 h-3 rounded-sm mr-2"
                        style={{ background: labelColorMap[lbl] }}
                      />
                      {lbl}: {val} ({totalLabels ? ((val / totalLabels) * 100).toFixed(1) : "0"}%)
                    </li>
                  ))}
                </ul>

                <p className="mt-3">Most Common: <strong>{mostCommon}</strong></p>
                <p>Accuracy (Factual): <strong>{factualRate}%</strong></p>
              </div>

              {/* RIGHT: OVERALL STACKED BAR */}
              <div className="lg:w-1/2 p-4 bg-white border rounded-md">
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={overallBarData}
                      onMouseLeave={() => setHoveredLabel(null)}
                    >
                      <XAxis dataKey="name" angle={-25} textAnchor="end" height={60} />
                      <YAxis />
                      <Tooltip
                        content={(props) => (
                          <CustomTooltip {...props} hoveredLabel={hoveredLabel} />
                        )}
                      />
                      <Legend />
                      {allLabels.map((lbl) => (
                        <Bar
                          key={lbl}
                          dataKey={lbl}
                          stackId="overall"
                          name={lbl}
                          fill={labelColorMap[lbl]}
                          onMouseOver={() => setHoveredLabel(lbl)}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

            </div>
          </CardContent>
        </Card>

        {/* =====================================================
             PER METRIC CARDS
           ===================================================== */}
        {metrics.map((metric) => {
          const counts = perMetricCounts[metric];
          const labels = Object.keys(counts);
          const donutData = labels.map((lbl) => ({
            name: lbl,
            value: counts[lbl],
            color: labelColorMap[lbl],
          }));

          const metricBarData = [
            labels.reduce((acc: any, lbl) => {
              acc.name = metric;
              acc[lbl] = counts[lbl];
              return acc;
            }, {}),
          ];

          return (
            <Card key={metric}>
              <CardHeader>
                <CardTitle>{metric}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col lg:flex-row gap-6">

                  {/* SUMMARY */}
                  <pre className="bg-white border rounded-md p-4 whitespace-pre-line flex-1">
                    {labels
                      .map((lbl) => {
                        const val = counts[lbl];
                        const pct = val
                          ? ((val / labels.reduce((s, k) => s + counts[k], 0)) * 100).toFixed(1)
                          : "0";
                        return `• ${lbl}: ${val} (${pct}%)`;
                      })
                      .join("\n")}
                  </pre>

                  {/* DONUT */}
                  <div className="flex-1 bg-white border rounded-md p-3 h-60">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={donutData}
                          innerRadius={40}
                          outerRadius={80}
                          dataKey="value"
                          label
                        >
                          {donutData.map((d) => (
                            <Cell key={d.name} fill={d.color} />
                          ))}
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>

                  {/* STACKED BAR */}
                  <div className="flex-1 bg-white border rounded-md p-3 h-60">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={metricBarData}
                        onMouseLeave={() => setHoveredLabel(null)}
                      >
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip
                          content={(props) => (
                            <CustomTooltip {...props} hoveredLabel={hoveredLabel} />
                          )}
                        />
                        <Legend />
                        {labels.map((lbl) => (
                          <Bar
                            key={lbl}
                            dataKey={lbl}
                            stackId="metric"
                            fill={labelColorMap[lbl]}
                            onMouseOver={() => setHoveredLabel(lbl)}
                          />
                        ))}
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                </div>
              </CardContent>
            </Card>
          );
        })}

        <div className="text-center">
          <Button
            onClick={() => navigate("/evaluation")}
            className="mt-4 bg-indigo-600 text-white"
          >
            Return to Dashboard
          </Button>
        </div>
      </main>

      <Outlet />
    </div>
  );
};

export default RAGOutput;
