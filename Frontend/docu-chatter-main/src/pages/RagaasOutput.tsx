import React, { useState, useMemo, useEffect } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { Download, ArrowLeft } from "lucide-react";
import { saveAs } from "file-saver";
import { useChatbots } from "@/hooks/useChatbots";

const RAGASEvaluationOutput: React.FC = () => {
    const navigate = useNavigate();
    const { id } = useParams<{ id: string }>();
    const location = useLocation();
    const { chatbots } = useChatbots();
    const { toast } = useToast();

    const [selectedMetric, setSelectedMetric] = useState<string>("All");
    const [showMore, setShowMore] = useState(false);
    //   const [displayedRows, setDisplayedRows] = useState<any[]>([]);

    const chatbot = chatbots.find((c) => c.id === id);
    const evaluationResponse = location.state?.evaluationResponse;

    const metrics = evaluationResponse?.metrics || [];
    const results = evaluationResponse?.results || {};

    // ✅ Function to shorten long text
    const truncateText = (text: string, length = 80) => {
        if (!text) return "N/A";
        return text.length > length ? text.slice(0, length) + "..." : text;
    };

    // ✅ Prepare all rows for all metrics
    const prepareRows = (metrics: string[], results: any) => {
        if (!metrics.length) return [];
        const rows = [];
        const maxRows = Math.max(...metrics.map((m) => results[m]?.length || 0));

        for (let i = 0; i < maxRows; i++) {
            const row: Record<string, any> = { "#": i + 1 };
            metrics.forEach((metric) => {
                const entry = results[metric]?.[i];
                const key = metric.toLowerCase().replace(/\s+/g, "_");
                row[metric] = entry
                    ? {
                        user_input: truncateText(entry.user_input),
                        response: truncateText(entry.response),
                        score:
                            entry[key] !== undefined
                                ? (entry[key]).toFixed(4)
                                : "N/A",
                        accuracy:
                            entry[key] !== undefined
                                ? ((entry[key] || 0) * 100).toFixed(2)
                                : "N/A",
                    }
                    : { user_input: "N/A", response: "N/A", score: "N/A", accuracy: "N/A" };
            });
            rows.push(row);
        }
        return rows;
    };

    const allRows = useMemo(() => prepareRows(metrics, results), [metrics, results]);

    // Compute filtered rows based on selected metric
    const filteredRows = useMemo(() => {
        if (selectedMetric === "All") return allRows;
        return allRows.map((row) => ({
            "#": row["#"],
            [selectedMetric]: row[selectedMetric],
        }));
    }, [allRows, selectedMetric]);

    // Compute displayed rows based on showMore
    const displayedRows = useMemo(() => {
        return showMore ? filteredRows : filteredRows.slice(0, 10);
    }, [filteredRows, showMore]);


    // ✅ Calculate average metric accuracies
    const metricAccuracies: Record<string, string> = useMemo(() => {
        const acc: Record<string, string> = {};
        metrics.forEach((metric) => {
            const metricResults = results[metric] || [];
            const key = metric.toLowerCase().replace(/\s+/g, "_");
            const validScores = metricResults
                .map((r: any) => r?.[key])
                .filter((v: number) => typeof v === "number" && !isNaN(v));
            const avg =
                validScores.length > 0
                    ? ((validScores.reduce((a, b) => a + b, 0) / validScores.length) * 100).toFixed(2)
                    : "N/A";
            acc[metric] = avg;
        });
        return acc;
    }, [metrics, results]);

    const exportCSV = () => {
        if (!chatbot) return;
        const headers = [
            "#",
            ...metrics.flatMap((m) => [`${m} Input`, `${m} Response`, `${m} Score`, `${m} Accuracy`]),
        ];
        const csvData = allRows.map((row) =>
            metrics.flatMap((m) => [
                row[m].user_input,
                row[m].response,
                row[m].score,
                row[m].accuracy,
            ])
        );
        const csvContent = [headers.join(","), ...csvData.map((r) => r.map((v) => `"${v}"`).join(","))].join("\n");
        saveAs(new Blob([csvContent], { type: "text/csv;charset=utf-8;" }), `${chatbot.name}_ragaas_results.csv`);
        toast({ title: "Export Successful", description: "CSV file downloaded." });
    };

    const exportJSON = () => {
        if (!chatbot) return;
        const data = { chatbot: chatbot.name, framework: evaluationResponse?.framework, metricAccuracies, data: allRows };
        saveAs(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), `${chatbot.name}_ragaas_results.json`);
        toast({ title: "Export Successful", description: "JSON file downloaded." });
    };

    // 🧱 Render fallback safely
    if (!evaluationResponse) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen text-gray-200 bg-[#0f0f10]">
                <h1 className="text-2xl font-semibold mb-2">No Evaluation Data Available</h1>
                <p className="text-gray-400 mb-4">
                    Please run a RAGAS evaluation for this chatbot.
                </p>
                <Button onClick={() => navigate(`/evaluation-selection/${chatbot?.id}`)}>
                    Run Evaluation
                </Button>
            </div>
        );
    }

    if (!chatbot) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#0f0f10] text-gray-200">
                {/* <div className="text-center">
                    <h1 className="text-2xl font-bold mb-4">Chatbot Not Found</h1>
                    <Button onClick={() => navigate("/")} variant="secondary">
                        <ArrowLeft className="h-4 w-4 mr-2" /> Back to Dashboard
                    </Button>
                </div> */}
            </div>
        );
    }

    // ✅ Main UI render
    return (
        <div className="min-h-screen bg-gradient-surface text-gray-200">
            <header className="border-b border-gray-800 bg-gradient-card mb-6 shadow-md">
                <div className="container mx-auto px-4 py-4 flex items-center gap-4 justify-between">
                    <div className="flex items-center gap-3">
                        <Button variant="ghost" size="icon" onClick={() => navigate(`/evaluation-selection/${id}`)}>
                            <ArrowLeft className="h-5 w-5 text-white" />
                        </Button>
                        <h1 className="text-2xl font-bold text-white">
                            {chatbot.name} – RAGAS Evaluation Results
                        </h1>
                    </div>
                    <div className="flex gap-3">
                        <Button
                            onClick={exportCSV}
                            className="flex items-center gap-2 bg-gradient-to-r from-indigo-500 to-purple-500 text-white hover:opacity-90"
                        >
                            <Download className="w-4 h-4" /> CSV
                        </Button>
                        <Button
                            onClick={exportJSON}
                            className="flex items-center gap-2 bg-gradient-to-r from-indigo-500 to-purple-500 text-white hover:opacity-90"
                        >
                            <Download className="w-4 h-4" /> JSON
                        </Button>
                    </div>
                </div>
            </header>

            <main className="container mx-auto px-4 space-y-6">
                {/* Metric Summary */}
                <Card className="shadow-elegant border border-gray-700 shadow-lg">
                    <CardHeader>
                        <CardTitle className="text-xl font-semibold text-gray-200">
                            Metric Averages
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-wrap gap-4">
                        {metrics.map((metric) => (
                            <div
                                key={metric}
                                onClick={() => setSelectedMetric(metric)}
                                className={`cursor-pointer rounded-lg px-4 py-3 border text-center flex-1 min-w-[150px] ${selectedMetric === metric
                                        ? "bg-indigo-600 border-indigo-500 text-white"
                                        : "bg-gradient-surface border-gray-700 hover:bg-gray-800"
                                    }`}
                            >
                                <div className="text-sm font-medium">{metric}</div>
                                <div className="text-lg font-bold">
                                    {metricAccuracies[metric]}%
                                </div>
                            </div>
                        ))}
                        <div
                            onClick={() => setSelectedMetric("All")}
                            className={`cursor-pointer rounded-lg px-4 py-3 border text-center flex-1 min-w-[150px] ${selectedMetric === "All"
                                    ? "bg-indigo-600 border-indigo-500 text-white"
                                    : "bg-gradient-surface border-gray-700 hover:bg-gray-800"
                                }`}
                        >
                            <div className="text-sm font-medium">All</div>
                            <div className="text-lg font-bold">View All</div>
                        </div>
                    </CardContent>
                </Card>

                {/* Evaluation Table */}
                <Card className="shadow-elegant border border-gray-700 shadow-md">
                    <CardHeader>
                        <CardTitle className="text-lg font-semibold text-gray-200">
                            Detailed Evaluation Results
                        </CardTitle>
                    </CardHeader>

                    <CardContent>
                        <div className="max-h-[400px] overflow-y-auto rounded-xl border border-gray-700">
                            <table className="min-w-full text-sm text-left text-gray-300">
                                <thead className="bg-gradient-surface text-gray-400 uppercase text-xs border-b border-gray-700">
                                    <tr>
                                        <th className="px-4 py-3">#</th>
                                        {selectedMetric === "All" ? (
                                            <>
                                                <th className="px-4 py-3">Input</th>
                                                <th className="px-4 py-3">Response</th>
                                                {metrics.map((metric) => (
                                                    <th key={metric} className="px-4 py-3">
                                                        {metric} Score (%)
                                                    </th>
                                                ))}
                                            </>
                                        ) : (
                                            <>
                                                <th className="px-4 py-3">Input</th>
                                                <th className="px-4 py-3">Response</th>
                                                <th className="px-4 py-3">Score</th>
                                                <th className="px-4 py-3">Accuracy</th>
                                            </>
                                        )}
                                    </tr>
                                </thead>

                                <tbody>
                                    {displayedRows.map((row, idx) => (
                                        <tr
                                            key={idx}
                                            className="border-b border-gray-700 hover:bg-gray-800 transition-all"
                                        >
                                            <td className="px-4 py-3">{row["#"]}</td>

                                            {selectedMetric === "All" ? (
                                                <>
                                                    {/* Show input and response only once per row */}
                                                    <td
                                                        className="px-4 py-3 max-w-[300px] truncate"
                                                        title={row[metrics[0]]?.user_input}
                                                    >
                                                        {row[metrics[0]]?.user_input}
                                                    </td>
                                                    <td
                                                        className="px-4 py-3 max-w-[300px] truncate"
                                                        title={row[metrics[0]]?.response}
                                                    >
                                                        {row[metrics[0]]?.response}
                                                    </td>

                                                    {/* Show each metric's score */}
                                                    {metrics.map((metric) => (
                                                        <td key={`${idx}-${metric}`} className="px-4 py-3 text-center">
                                                            {row[metric]?.score ?? "N/A"}
                                                        </td>
                                                    ))}
                                                </>
                                            ) : (
                                                <>
                                                    <td
                                                        className="px-4 py-3 max-w-[300px] truncate"
                                                        title={row[selectedMetric]?.user_input}
                                                    >
                                                        {row[selectedMetric]?.user_input}
                                                    </td>
                                                    <td
                                                        className="px-4 py-3 max-w-[300px] truncate"
                                                        title={row[selectedMetric]?.response}
                                                    >
                                                        {row[selectedMetric]?.response}
                                                    </td>
                                                    <td className="px-4 py-3">{row[selectedMetric]?.score}</td>
                                                    <td className="px-4 py-3">{row[selectedMetric]?.accuracy}</td>
                                                </>
                                            )}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {filteredRows.length > 10 && (
                            <div className="flex justify-center mt-4">
                                <Button
                                    variant="secondary"
                                    className="bg-gray-800 hover:bg-gray-700 text-white px-6 py-2 rounded-lg"
                                    onClick={() => setShowMore(!showMore)}
                                >
                                    {showMore ? "Show Less" : "Show More"}
                                </Button>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </main>
        </div>
    );
};

export default RAGASEvaluationOutput;
