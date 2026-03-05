import React, { useState, useMemo, useEffect } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useConfigOptions } from "@/hooks/useConfigOptions";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import {
    Download,
    ArrowLeft,
    BarChart2,
    CheckCircle2,
    XCircle,
    FileText,
    Eye,
    Target
} from "lucide-react";
import { saveAs } from "file-saver";
import { useChatbots } from "@/hooks/useChatbots";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    Legend,
    CartesianGrid,
    Cell
} from "recharts";
import { cn } from "@/lib/utils";

// --- Types ---
interface RagasRow {
    "#": number;
    [key: string]: any;
}

// --- Colors ---
const CHART_COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff8042", "#a4de6c", "#d0ed57", "#ffc658"];

const RAGASEvaluationOutput: React.FC = () => {
    const navigate = useNavigate();
    const { id } = useParams<{ id: string }>();
    const location = useLocation();
    const { chatbots } = useChatbots();
    const { toast } = useToast();
    const [searchParams] = useSearchParams();
    const evalId = searchParams.get("evalId");
    const { config } = useConfigOptions();

    const [selectedMetric, setSelectedMetric] = useState<string>("All");
    const [showMore, setShowMore] = useState(false);
    const [apiData, setApiData] = useState<any>(null);
    const [loading, setLoading] = useState<boolean>(() => {
        return !location.state?.evaluationResponse && !!evalId && !!config?.base_url;
    });

    const [selectedRecord, setSelectedRecord] = useState<any>(null); // For Modal

    useEffect(() => {
        if (!location.state?.evaluationResponse && evalId && config?.base_url) {
            setLoading(true);
            fetch(`${config.base_url}/evaluation/evaluation-status/${evalId}`)
                .then((res) => res.json())
                .then((data) => {
                    setApiData(data);
                })
                .catch((err) => {
                    console.error(err);
                    toast({ title: "Error", description: "Failed to load evaluation data", variant: "destructive" });
                })
                .finally(() => setLoading(false));
        }
    }, [location.state, evalId, config]);

    const chatbot = chatbots.find((c) => String(c.id) === String(id));
    const evaluationResponse = location.state?.evaluationResponse || apiData;

    const metrics: string[] = evaluationResponse?.metrics || [];
    const results = evaluationResponse?.results || {};

    const truncateText = (text: string, length = 60) => {
        if (!text) return "N/A";
        return text.length > length ? text.slice(0, length) + "..." : text;
    };

    // Γ£à Prepare all rows for all metrics
    const prepareRows = (metrics: string[], results: any): RagasRow[] => {
        if (!metrics.length) return [];
        const rows: RagasRow[] = [];
        const maxRows = Math.max(...metrics.map((m) => results[m]?.length || 0));

        for (let i = 0; i < maxRows; i++) {
            const row: RagasRow = { "#": i + 1 };
            // Base record info (assuming aligned)
            const baseMetric = metrics[0];
            const baseEntry = results[baseMetric]?.[i];

            row["common"] = {
                user_input: baseEntry?.question || baseEntry?.user_input || baseEntry?.query || "N/A",
                response: baseEntry?.answer || baseEntry?.response || baseEntry?.output || "N/A",
                contexts: baseEntry?.contexts || baseEntry?.context || baseEntry?.retrieved_contexts || baseEntry?.reference || [],
                ground_truth: baseEntry?.ground_truth || baseEntry?.ground_truths || baseEntry?.reference || "N/A",
            };

            metrics.forEach((metric) => {
                const entry = results[metric]?.[i];
                const key = metric.toLowerCase().replace(/\s+/g, "_");
                // Find numeric key if possible (faithfulness, answer_relevancy etc)
                // Ragas often returns key same as metric name or slightly varied
                // We try matching distinct numeric keys or fallback

                let scoreVal = "N/A";
                // Try to find the score value in the entry object
                if (entry) {
                    // entry like { question:..., answer:..., faithfulness: 0.8 }
                    // Try exact key
                    if (entry[key] !== undefined) scoreVal = entry[key];
                    // Try metric name
                    else if (entry[metric.toLowerCase()] !== undefined) scoreVal = entry[metric.toLowerCase()];
                    // Try looking for any float property that isn't standard fields
                    else {
                        const potentialKey = Object.keys(entry).find(k =>
                            !["question", "answer", "contexts", "ground_truth", "user_input", "response"].includes(k) &&
                            typeof entry[k] === 'number'
                        );
                        if (potentialKey) scoreVal = entry[potentialKey];
                    }
                }

                row[metric] = {
                    score: scoreVal !== "N/A" ? Number(scoreVal).toFixed(4) : "N/A",
                };
            });
            rows.push(row);
        }
        return rows;
    };

    const allRows = useMemo(() => prepareRows(metrics, results), [metrics, results]);

    // Γ£à Calculate average metric accuracies for Charts
    const metricAverages = useMemo(() => {
        return metrics.map((metric) => {
            const rowScores = allRows.map((r) => parseFloat(r[metric]?.score)).filter((s) => !isNaN(s));
            const avg = rowScores.length ? rowScores.reduce((a, b) => a + b, 0) / rowScores.length : 0;
            return {
                name: metric,
                value: parseFloat((avg * 100).toFixed(2)), // Convert to 0-100 scale generally for display
                rawAvg: avg.toFixed(4)
            };
        });
    }, [allRows, metrics]);


    const exportCSV = () => {
        if (!chatbot) return;
        // Simple Export Logic
        const headers = ["#", "Question", "Response", ...metrics.map(m => `${m} Score`)];
        const rows = allRows.map(r => [
            r["#"],
            `"${r.common.user_input.replace(/"/g, '""')}"`,
            `"${r.common.response.replace(/"/g, '""')}"`,
            ...metrics.map(m => r[m]?.score)
        ]);
        const csvContent = [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
        saveAs(new Blob([csvContent], { type: "text/csv;charset=utf-8;" }), `${chatbot.name}_ragas_results.csv`);
        toast({ title: "Export Successful" });
    };

    const displayedRows = showMore ? allRows : allRows.slice(0, 10);

    if (loading) return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-background text-foreground">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4" />
            <p>Loading Evaluation...</p>
        </div>
    );

    if (!evaluationResponse || !chatbot) return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-background text-foreground">
            <h1 className="text-2xl font-bold">No Data Found</h1>
            <Button onClick={() => navigate("/")} className="mt-4">Back Home</Button>
        </div>
    );

    return (
        <div className="min-h-screen bg-background text-foreground animate-in fade-in duration-500">
            {/* BACKGROUND */}
            <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
                <div className="absolute top-0 -left-64 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[100px]" />
                <div className="absolute bottom-0 -right-64 w-[600px] h-[600px] bg-secondary/5 rounded-full blur-[100px]" />
            </div>

            <div className="relative z-10 flex flex-col min-h-screen max-w-[1600px] mx-auto p-6 space-y-8">
                {/* HEAD */}
                <header className="bg-background/80 backdrop-blur-xl border-b border-white/10 rounded-xl sticky top-4 z-50 overflow-hidden">
                    <div className="flex items-center justify-between px-8 h-20">
                        <div className="flex items-center gap-5">
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => navigate(`/evaluation-selection/${id}`)}
                                className="hover:bg-primary/10 hover:text-primary transition-colors rounded-xl w-10 h-10"
                            >
                                <ArrowLeft className="w-5 h-5" />
                            </Button>
                            <div className="flex flex-col">
                                <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-gray-100 to-gray-400 tracking-tight">
                                    {chatbot.name}
                                </h1>
                                <span className="text-sm text-muted-foreground font-medium tracking-wide">
                                    RAGAS Evaluation Report
                                </span>
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={exportCSV}
                                className="hidden sm:flex border-white/10 hover:border-primary/50 hover:bg-primary/5 text-sm gap-2 rounded-xl px-4 h-9"
                            >
                                <BarChart2 className="w-4 h-4" />
                                Export CSV
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                    saveAs(
                                        new Blob([JSON.stringify(evaluationResponse, null, 2)], { type: "application/json" }),
                                        `${chatbot.name}_ragas_results.json`
                                    );
                                    toast({ title: "JSON Exported Successfully" });
                                }}
                                className="hidden sm:flex border-white/10 hover:border-secondary/50 hover:bg-secondary/5 text-sm gap-2 rounded-xl px-4 h-9"
                            >
                                <FileText className="w-4 h-4" />
                                Export JSON
                            </Button>
                            <Button
                                variant="default"
                                size="sm"
                                onClick={() => navigate(`/evaluation-selection/${id}`)}
                                className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 text-sm font-semibold rounded-xl px-5 h-9"
                            >
                                Back to Evaluation
                            </Button>
                        </div>
                    </div>
                    <div className="h-[1px] w-full bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
                </header>

                {/* CHARTS & STATS */}
                <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Left: Score Cards */}
                    <div className="space-y-4 lg:col-span-1">
                        <div className="grid grid-cols-2 gap-4">
                            {metricAverages.map((m, idx) => (
                                <Card key={m.name} className="bg-white/5 border-white/10 hover:border-primary/50 transition-colors group">
                                    <CardHeader className="pb-2">
                                        <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">{m.name}</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-2xl font-bold text-foreground group-hover:text-primary transition-colors">
                                            {m.value}%
                                        </div>
                                        <p className="text-xs text-muted-foreground mt-1">
                                            Avg Score: {m.rawAvg}
                                        </p>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </div>

                    {/* Right: Chart */}
                    <Card className="lg:col-span-2 bg-white/5 border-white/10">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <BarChart2 className="w-5 h-5 text-primary" />
                                Metric Performance Overview
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="h-[250px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={metricAverages} barSize={40}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                                    <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                                    <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} domain={[0, 100]} />
                                    <Tooltip
                                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                        contentStyle={{ backgroundColor: '#1e293b', borderColor: 'rgba(255,255,255,0.1)', color: '#fff' }}
                                    />
                                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                                        {metricAverages.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </section>

                {/* MAIN TABLE */}
                <Card className="bg-white/5 border-white/10 overflow-hidden">
                    <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle className="text-lg">Detailed Records</CardTitle>
                        <Button variant="ghost" size="sm" onClick={() => setShowMore(!showMore)}>
                            {showMore ? "Show Less" : "Show All"}
                        </Button>
                    </CardHeader>
                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader className="bg-black/20">
                                <TableRow className="border-white/5 hover:bg-transparent">
                                    <TableHead className="w-[50px]">#</TableHead>
                                    <TableHead className="w-[300px]">Question</TableHead>
                                    <TableHead className="w-[300px]">Response</TableHead>
                                    {metrics.map(m => (
                                        <TableHead key={m} className="text-right whitespace-nowrap">{m}</TableHead>
                                    ))}
                                    <TableHead className="w-[100px] text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {displayedRows.map((row, idx) => (
                                    <TableRow key={idx} className="border-white/5 hover:bg-white/5 transition-colors">
                                        <TableCell className="font-mono text-xs text-muted-foreground">{row["#"]}</TableCell>
                                        <TableCell className="font-medium">
                                            <div className="line-clamp-2" title={row.common.user_input}>
                                                {row.common.user_input}
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-muted-foreground">
                                            <div className="line-clamp-2" title={row.common.response}>
                                                {row.common.response}
                                            </div>
                                        </TableCell>
                                        {metrics.map(m => (
                                            <TableCell key={m} className="text-right font-mono">
                                                <span className={cn(
                                                    "px-2 py-1 rounded text-xs font-bold",
                                                    Number(row[m]?.score) > 0.7 ? "bg-green-500/10 text-green-500" :
                                                        Number(row[m]?.score) < 0.3 ? "bg-red-500/10 text-red-500" : "bg-yellow-500/10 text-yellow-500"
                                                )}>
                                                    {row[m]?.score}
                                                </span>
                                            </TableCell>
                                        ))}
                                        <TableCell className="text-right">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => setSelectedRecord(row)}
                                                className="hover:bg-primary/20 hover:text-primary"
                                            >
                                                <Eye className="w-4 h-4" />
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                </Card>

                {/* DETAILS MODAL */}
                <Dialog open={!!selectedRecord} onOpenChange={(open) => !open && setSelectedRecord(null)}>
                    <DialogContent className="max-w-[95vw] w-[1400px] max-h-[90vh] flex flex-col bg-background/95 backdrop-blur-md border-white/10 p-6 overflow-hidden">
                        <DialogHeader>
                            <DialogTitle className="text-xl font-bold flex items-center gap-2">
                                <FileText className="w-5 h-5 text-primary" />
                                Record Details #{selectedRecord?.["#"]}
                            </DialogTitle>
                        </DialogHeader>
                        <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
                            {selectedRecord && (
                                <div className="space-y-6">
                                    {/* QA Section */}
                                    <div className="grid gap-4">
                                        <div className="bg-white/5 p-4 rounded-lg border border-white/5">
                                            <h3 className="text-sm font-semibold text-muted-foreground mb-2 flex items-center gap-2">
                                                <CheckCircle2 className="w-4 h-4 text-primary" /> Question
                                            </h3>
                                            <p className="text-foreground leading-relaxed whitespace-pre-wrap">{selectedRecord.common.user_input}</p>
                                        </div>

                                        <div className="bg-white/5 p-4 rounded-lg border border-white/5">
                                            <h3 className="text-sm font-semibold text-muted-foreground mb-2 flex items-center gap-2">
                                                <Target className="w-4 h-4 text-secondary" /> Response
                                            </h3>
                                            <p className="text-foreground leading-relaxed whitespace-pre-wrap">{selectedRecord.common.response}</p>
                                        </div>
                                    </div>

                                    {/* Metrics Breakdown */}
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                                        {metrics.map(m => (
                                            <div key={m} className="bg-black/20 p-3 rounded-lg border border-white/5 text-center">
                                                <p className="text-xs text-muted-foreground uppercase mb-1">{m}</p>
                                                <p className="text-xl font-bold text-primary">{selectedRecord[m]?.score}</p>
                                            </div>
                                        ))}
                                    </div>

                                    {/* Ground Truth & Contexts */}
                                    <div className="space-y-4">
                                        <div className="bg-white/5 p-4 rounded-lg border border-white/5">
                                            <h3 className="text-sm font-semibold text-muted-foreground mb-2">Ground Truth</h3>
                                            <p className="text-sm text-foreground/80">{selectedRecord.common.ground_truth || "N/A"}</p>
                                        </div>

                                        <div className="bg-white/5 p-4 rounded-lg border border-white/5">
                                            <h3 className="text-sm font-semibold text-muted-foreground mb-2">Retrieved Contexts</h3>
                                            {selectedRecord.common.contexts?.length > 0 ? (
                                                <ul className="space-y-2">
                                                    {selectedRecord.common.contexts.map((ctx: string, idx: number) => (
                                                        <li key={idx} className="text-sm text-foreground/80 bg-black/20 p-2 rounded border-l-2 border-primary/50">
                                                            {ctx}
                                                        </li>
                                                    ))}
                                                </ul>
                                            ) : (
                                                <p className="text-sm text-muted-foreground italic">No contexts retrieved.</p>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </DialogContent>
                </Dialog>

            </div>
        </div>
    );
};

export default RAGASEvaluationOutput;
