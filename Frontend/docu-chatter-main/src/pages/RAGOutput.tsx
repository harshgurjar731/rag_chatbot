import { useNavigate, useLocation, useParams, Outlet } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Download, FileText } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useChatbots } from "@/hooks/useChatbots";
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip,
  BarChart, Bar, XAxis, YAxis, Legend
} from "recharts";
import { saveAs } from "file-saver";

const THEME_COLORS = {
  indigo: "#6366f1",
  purple: "#8b5cf6",
  pink: "#ec4899",
  yellow: "#facc15",
};

const RAGOutput = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { id } = useParams<{ id: string }>();
  const { getChatbot } = useChatbots();
  const chatbot = id ? getChatbot(id) : null;
  const location = useLocation();
  const apiResponse = location.state?.evaluationResponse;

  if (!chatbot)
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-surface">
        {/* <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Chatbot Not Found</h1>
          <Button onClick={() => navigate("/")} variant="chatbot">
            <ArrowLeft className="h-4 w-4" /> Back to Dashboard
          </Button>
        </div> */}
      </div>
    );

  if (!apiResponse)
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-surface">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">No Evaluation Data</h1>
          <Button onClick={() => navigate(`/evaluation-selection/${id}`)}>Go Back</Button>
        </div>
      </div>
    );

  const metrics = apiResponse.metrics || Object.keys(apiResponse.results || {});

  const normalizeValue = (val: string | null | undefined) =>
    val && val.toLowerCase() !== "unknown" ? val : null;

  // Build textual summary per record dynamically
  const buildTextualSummary = (metric: string, record: any, metricData: any) => {
    const counts: Record<string, number> = {};
    Object.keys(record)
      .filter((k) => k.endsWith("_eval"))
      .forEach((key) => {
        const val = normalizeValue(record[key]);
        if (val) counts[val] = (counts[val] || 0) + 1;
      });

    const totalValid = Object.values(counts).reduce((a, b) => a + b, 0);
    const mostCommon = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || "N/A";

    return `
Metric: ${metric}
Total Records: ${metricData?.total_records || 1}
${Object.entries(counts)
        .map(([label, val]) => `${label}: ${val} (${((val / totalValid) * 100).toFixed(1)}%)`)
        .join("\n")}
Most Frequent Outcome: ${mostCommon}
Model Used: ${metricData?.model_used || "Unknown"}
`;
  };

  // Prepare export data with only metrics values + necessary meta
  const prepareExportData = () => {
    const rows: any[] = [];
    metrics.forEach((metric) => {
      const metricData = apiResponse.results[metric];
      const results = metricData?.results || [];
      results.forEach((r: any, idx: number) => {
        const row: Record<string, any> = {
          metric,
          record_index: idx + 1,
          framework: apiResponse.framework,
          progress: apiResponse.progress,
          status: apiResponse.status,
          model_used: metricData?.model_used || "Unknown",
          textual_summary: buildTextualSummary(metric, r, metricData),
        };

        // Include only valid metric evaluation keys
        Object.keys(r)
          .filter((k) => k.endsWith("_eval"))
          .forEach((key) => {
            const val = normalizeValue(r[key]);
            if (val) row[key] = val;
          });

        rows.push(row);
      });
    });
    return rows;
  };

  // Export CSV
  const exportCSV = () => {
    const data = prepareExportData();
    if (!data.length) {
      toast({ title: "No data to export" });
      return;
    }

    const headers = Object.keys(data[0]);
    let csv = headers.join(",") + "\n";

    data.forEach((row) => {
      const values = headers.map((h) =>
        `"${(row[h] || "").toString().replace(/"/g, '""')}"`
      );
      csv += values.join(",") + "\n";
    });

    saveAs(
      new Blob([csv], { type: "text/csv;charset=utf-8;" }),
      `${chatbot.name}_evaluation_metrics.csv`
    );
    toast({ title: "CSV exported successfully!" });
  };

  // Export JSON
  const exportJSON = () => {
    const data = prepareExportData();
    saveAs(
      new Blob([JSON.stringify({ meta: apiResponse, results: data }, null, 2)], { type: "application/json" }),
      `${chatbot.name}_evaluation_metrics.json`
    );
    toast({ title: "JSON exported successfully!" });
  };


  // Prepare overall summary counts
  // const overallCounts: Record<string, number> = {};
  // metrics.forEach((metric) => {
  //   const metricData = apiResponse.results[metric];
  //   const results = metricData?.results || [];
  //   results.forEach((r: any) => {
  //     Object.keys(r)
  //       .filter((k) => k.endsWith("_eval"))
  //       .forEach((key) => {
  //         const val = normalizeValue(r[key]);
  //         overallCounts[val] = (overallCounts[val] || 0) + 1;
  //       });
  //   });
  // });

  // const overallPieData = Object.entries(overallCounts).map(([name, value], idx) => ({
  //   name, value,
  //   color: THEME_COLORS[Object.keys(THEME_COLORS)[idx % Object.keys(THEME_COLORS).length]],
  // }));

  // const overallBarData = Object.entries(overallCounts).map(([name, value]) => ({ name, value }));
  const overallPieData = metrics.flatMap((metric) => {
    const metricData = apiResponse.results[metric];
    const results = metricData?.results || [];

    // Count per label
    const counts: Record<string, number> = {};
    results.forEach((r: any) => {
      Object.keys(r)
        .filter((k) => k.endsWith("_eval"))
        .forEach((key) => {
          const val = normalizeValue(r[key]);
          if (val && val.toLowerCase() !== "unknown") {
            counts[val] = (counts[val] || 0) + 1;
          }
        });
    });

    // Transform into pie chart friendly format
    return Object.entries(counts).map(([label, value], idx) => ({
      name: `${metric}: ${label}`, // 👈 metric name included
      value,
      color:
        THEME_COLORS[
        Object.keys(THEME_COLORS)[idx % Object.keys(THEME_COLORS).length]
        ],
    }));
  });

  const overallBarData = metrics.flatMap((metric) => {
    const metricData = apiResponse.results[metric];
    const results = metricData?.results || [];

    // Count per label
    const counts: Record<string, number> = {};
    results.forEach((r: any) => {
      Object.keys(r)
        .filter((k) => k.endsWith("_eval"))
        .forEach((key) => {
          const val = normalizeValue(r[key]);
          if (val && val.toLowerCase() !== "unknown") {
            counts[val] = (counts[val] || 0) + 1;
          }
        });
    });

    // Transform into bar-friendly format
    return Object.entries(counts).map(([label, value], idx) => ({
      name: `${metric}: ${label}`, // 👈 include metric
      value,
      color:
        THEME_COLORS[
        Object.keys(THEME_COLORS)[idx % Object.keys(THEME_COLORS).length]
        ],
    }));
  });

  return (
    <div className="min-h-screen bg-gradient-surface text-foreground">
      {/* Header */}
      <header className="border-b border-chatbot-primary/20 bg-gradient-card">
        <div className="container mx-auto px-4 py-4 flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(`/evaluation-selection/${id}`)}>
            <ArrowLeft className="h-5 w-5 text-foreground" />
          </Button>
          <h1 className="text-3xl font-bold">{chatbot.name} – Evaluation Results</h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-10">

        {/* Export buttons */}
        <div className="flex gap-4 justify-end">
          <Button onClick={exportCSV} className="flex items-center gap-2 bg-indigo-500 text-white px-4 py-2 rounded-md">
            <Download className="w-4 h-4" /> Export Complete CSV
          </Button>
          <Button onClick={exportJSON} className="flex items-center gap-2 bg-green-500 text-white px-4 py-2 rounded-md">
            <FileText className="w-4 h-4" /> Export JSON
          </Button>
        </div>

        {/* Overall summary */}
        <Card className="shadow-elegant w-full h-full p-4">
          <CardHeader>
            <CardTitle className="text-2xl">Overall Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">

            <div className="lg:flex lg:flex-row gap-8">

              {/* Overall Pie Chart */}
              <div className="flex-1 h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={overallPieData.filter(
                        (d) => d.name && d.name.toLowerCase() !== "unknown"
                      )}
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      label={({ name, value }) => `${name}: ${value}`}
                      labelLine={true}
                      dataKey="value"
                      fontSize={14}
                    >
                      {overallPieData
                        .filter((d) => d.name && d.name.toLowerCase() !== "unknown")
                        .map((entry, idx) => (
                          <Cell key={idx} fill={entry.color} />
                        ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Overall Bar Chart */}
              <div className="flex-1 h-60">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={overallBarData}>
                    <XAxis
                      dataKey="name"
                      interval={0}
                      angle={-20}
                      textAnchor="end"
                      height={80}
                      fontSize={12}
                    />
                    <YAxis />
                    <Tooltip />
                    {/* <Legend /> */}
                    <Bar dataKey="value"
                      isAnimationActive={true}
                      animationDuration={800}
                      animationEasing="ease-out"
                      // barSize={30}
                      // fill="#8884d8"
                      label={{ position: 'top', fontSize: 14 }}
                    >
                      {overallBarData.map((entry, idx) => (
                        <Cell key={idx} fill={entry.color}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

            </div>

            {/* Overall Textual Summary (moved below charts) */}
            {/* <div className="bg-gray-50 p-4 rounded-md whitespace-pre-wrap mt-6">
      {metrics.length > 0 ? (
        <>
          <p>Total Metrics Evaluated: {metrics.length}</p>
          <p>
            Total Records:{" "}
            {metrics.reduce(
              (sum, metric) => sum + (apiResponse.results[metric]?.total_records || 0),
              0
            )}
          </p>
          <p>Most Common Outcomes Per Metric:</p>
          <ul className="list-disc ml-6">
            {metrics.map((metric) => {
              const results = apiResponse.results[metric]?.results || [];
              const counts: Record<string, number> = {};
              results.forEach((r: any) => {
                Object.keys(r)
                  .filter((k) => k.endsWith("_eval"))
                  .forEach((key) => {
                    const val = r[key];
                    if (val && val.toLowerCase() !== "unknown") {
                      counts[val] = (counts[val] || 0) + 1;
                    }
                  });
              });
              const mostFrequent = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
              return (
                <li key={metric}>
                  {metric}: {mostFrequent || "N/A"}
                </li>
              );
            })}
          </ul>
        </>
      ) : (
        <p>No metrics data available.</p>
      )}
    </div> */}

          </CardContent>
        </Card>

        {/* Metric-wise row: Text | Pie | Bar */}
        {/* {metrics.map((metric) => {
          const metricData = apiResponse.results[metric];
          const results = metricData?.results || [];
          const totalRecords = metricData?.total_records || results.length;

          const counts: Record<string, number> = {};
          results.forEach((r: any) => {
            Object.keys(r)
              .filter((k) => k.endsWith("_eval"))
              .forEach((key) => {
                const val = normalizeValue(r[key]);
                counts[val] = (counts[val] || 0) + 1;
              });
          }); */}
        {metrics.map((metric) => {
          const metricData = apiResponse.results[metric];
          const results = metricData?.results || [];
          const totalRecords = metricData?.total_records || results.length;

          const counts: Record<string, number> = {};
          results.forEach((r: any) => {
            Object.keys(r)
              .filter((k) => k.endsWith("_eval"))
              .forEach((key) => {
                const val = normalizeValue(r[key]);
                if (val && val.toLowerCase() !== "unknown") {  // ✅ filter invalid
                  counts[val] = (counts[val] || 0) + 1;
                }
              });
          });


          // Calculate total counted labels (excluding unknowns)
          const countedTotal = Object.entries(counts)
            .filter(([label, val]) => val && label.toLowerCase() !== "unknown")
            .reduce((sum, [, val]) => sum + val, 0);

          // Determine the most common label dynamically
          const mostCommon = Object.entries(counts)
            .filter(([label, val]) => val && label.toLowerCase() !== "unknown")
            .sort((a, b) => b[1] - a[1])[0]?.[0] || "N/A";

          // Generate dynamic descriptions for known labels
          const getLabelDescription = (label: string) => {
            switch (label.toLowerCase()) {
              case "factual":
                return "✔️ Correct based on reference";
              case "hallucinated":
                return "❌ Incorrect or unsupported answer";
              case "neutral":
                return "➖ Partial or inconclusive result";
              case "relevant":
                return "🔎 Contextually relevant";
              case "irrelevant":
                return "🚫 Irrelevant to query";
              case "non-toxic":
                return "🟢 Safe content";
              case "toxic":
                return "⚠️ May contain harmful content";
              default:
                return "";
            }
          };

          // Build textual summary
          const textualSummary = `
📌 Metric: ${metric}
────────────────────────────
Total Records: ${totalRecords}

${Object.entries(counts)
              .filter(([label, val]) => val && label.toLowerCase() !== "unknown")
              .map(([label, val]) => {
                const percentage = countedTotal ? ((val / countedTotal) * 100).toFixed(1) : "0";
                const description = getLabelDescription(label);
                return `• ${label}: ${val} (${percentage}%) ${description ? `→ ${description}` : ""}`;
              })
              .join("\n")}

🌟 Most Common Outcome: ${mostCommon}
📈 Accuracy Estimate: ${countedTotal ? `${((counts.factual || 0) / countedTotal * 100).toFixed(1)}%` : "N/A"}
🧠 Model Used: ${metricData?.model_used || "Unknown"}
`;




          const pieData = Object.entries(counts).map(([name, value], idx) => ({
            name, value,
            color: THEME_COLORS[Object.keys(THEME_COLORS)[idx % Object.keys(THEME_COLORS).length]],
          }));

          const barData = Object.entries(counts).map(([name, value]) => ({ name, value }));

          return (
            <Card key={metric} className="shadow-elegant">
              <CardHeader>
                <CardTitle className="text-2xl">{metric}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col lg:flex-row gap-6">
                  <pre className="flex-1 whitespace-pre-line bg-gray-50 text-gray-800 p-4 rounded-md border border-gray-200">
                    {textualSummary && textualSummary.trim() !== "" ? textualSummary : "No summary available"}
                  </pre>
                  <div className="flex-1 h-60">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={pieData}
                          cx="50%"
                          cy="50%"
                          outerRadius={80}
                          label={({ name, value }) => `${name}: ${value}`}
                          labelLine={false}
                          dataKey="value"

                          fontSize={14}
                        >
                          {pieData.map((entry, idx) => <Cell key={idx} fill={entry.color} />)}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="flex-1 h-60">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barData}><XAxis
                        dataKey="name"
                        interval={0}
                        angle={-30}
                        textAnchor="end"
                        height={80}
                        fontSize={14}
                      />
                        <YAxis />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="value" fill={THEME_COLORS.purple}
                          fontSize={12} >
                          {barData.map((entry, idx) => <Cell key={idx} fill={THEME_COLORS[Object.keys(THEME_COLORS)[idx % Object.keys(THEME_COLORS).length]]} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })
        }

        <div className="flex justify-center">
          <Button
            onClick={() => navigate("/evaluation")}
            className="bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 text-white px-6 py-3 rounded-xl shadow-lg hover:opacity-90"
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
