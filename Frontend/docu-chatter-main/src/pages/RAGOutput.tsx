import React, { useState } from "react";
import { useNavigate, useLocation, useParams, Outlet } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ArrowLeft,
  Download,
  FileText,
  BarChart2,
  PieChart as PieChartIcon,
  CheckCircle2,
  AlertCircle,
  Activity,
  Layers,
  Target,
  FileJson,
} from "lucide-react";
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

// ... existing imports ...

// New Component: Detailed Records Modal
const RecordsTableModal = ({
  apiResponse,
  chatbotName,
}: {
  apiResponse: any;
  chatbotName: string;
}) => {
  if (!apiResponse || !apiResponse.results) return null;

  const metrics = Object.keys(apiResponse.results);
  if (metrics.length === 0) return null;

  // Aggregate Data
  // Assumption: All metrics return results in the same order (aligned by row index)
  // We'll take the first metric's results as the base for questions/responses
  const baseMetric = metrics[0];
  const baseResults = apiResponse.results[baseMetric]?.results || [];

  const aggregatedRecords = baseResults.map((record: any, idx: number) => {
    const row: any = {
      question: record.query || record.question || "N/A",
      response: record.response || record.answer || "N/A",
      metrics: {},
    };

    metrics.forEach((m) => {
      const mResults = apiResponse.results[m]?.results;
      if (mResults && mResults[idx]) {
        row.metrics[m] = mResults[idx].label || "N/A";
      } else {
        row.metrics[m] = "N/A";
      }
    });

    return row;
  });

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <FileJson className="w-3.5 h-3.5" />
          View Records
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-[90vw] w-full max-h-[85vh] flex flex-col bg-background/95 backdrop-blur-md border-white/10">
        <DialogHeader>
          <DialogTitle>Evaluation Records - {chatbotName}</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-auto mt-4 border rounded-md border-white/10 custom-scrollbar">
          <Table>
            <TableHeader className="sticky top-0 bg-background z-10">
              <TableRow className="hover:bg-transparent border-white/10">
                <TableHead className="w-[300px] text-foreground font-semibold">
                  Question
                </TableHead>
                <TableHead className="w-[400px] text-foreground font-semibold">
                  Response
                </TableHead>
                {metrics.map((m) => (
                  <TableHead
                    key={m}
                    className="capitalize text-foreground font-semibold min-w-[120px]"
                  >
                    {m.replace(/_/g, " ")}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {aggregatedRecords.map((row: any, i: number) => (
                <TableRow
                  key={i}
                  className="border-white/5 hover:bg-white/5 transition-colors"
                >
                  <TableCell className="font-medium align-top py-4">
                    {row.question}
                  </TableCell>
                  <TableCell className="text-muted-foreground align-top py-4">
                    <div className="max-h-[100px] overflow-y-auto custom-scrollbar pr-2 text-sm">
                      {row.response}
                    </div>
                  </TableCell>
                  {metrics.map((m) => (
                    <TableCell key={m} className="align-top py-4">
                      <span
                        className={cn(
                          "px-2 py-1 rounded-md text-xs font-medium border",
                          row.metrics[m] === "factual" ||
                            row.metrics[m] === "relevant"
                            ? "bg-success/10 text-success border-success/20"
                            : row.metrics[m] === "hallucinated" ||
                              row.metrics[m] === "irrelevant"
                              ? "bg-destructive/10 text-destructive border-destructive/20"
                              : "bg-secondary/10 text-secondary border-secondary/20"
                        )}
                      >
                        {row.metrics[m]}
                      </span>
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  );
};

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
  AreaChart,
  Area,
  CartesianGrid,
} from "recharts";
import { saveAs } from "file-saver";
import { cn } from "@/lib/utils";

/**
 * ------------------------------------------------------------------
 * UTILS & CONSTANTS
 * ------------------------------------------------------------------
 */

// Neon/Dark Theme Palette aligned with index.css
// Cool-Tone / Complimentary Theme Palette (No harsh contrasts)
const COLORS = {
  primary: "#38bdf8", // Sky Blue
  secondary: "#818cf8", // Soft Indigo
  success: "#2dd4bf", // Teal
  warning: "#60a5fa", // Blue (used instead of amber)
  info: "#c084fc", // Purple
  danger: "#94a3b8", // Slate (used instead of red)
  neutral: "#64748b", // Dark Slate
};

const CHART_PALETTE = [
  "#38bdf8", // Sky
  "#818cf8", // Indigo
  "#2dd4bf", // Teal
  "#c084fc", // Purple
  "#22d3ee", // Cyan
  "#60a5fa", // Blue
  "#94a3b8", // Slate
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="bg-popover/95 border border-border p-3 rounded-lg shadow-xl backdrop-blur-sm">
      <p className="font-semibold text-foreground mb-2">{label}</p>
      {payload.map((entry: any, index: number) => (
        <div key={index} className="flex items-center gap-2 text-sm">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-muted-foreground capitalize">{entry.name}:</span>
          <span className="text-foreground font-mono font-medium">
            {entry.value}
          </span>
        </div>
      ))}
    </div>
  );
};

// Metric Card with Flip Effect
const MetricFlipCard = ({
  metric,
  counts,
  labelColorMap,
  index,
}: {
  metric: string;
  counts: Record<string, number>;
  labelColorMap: Record<string, string>;
  index: number;
}) => {
  const [isFlipped, setIsFlipped] = useState(false);

  const data = Object.entries(counts).map(([k, v]) => ({
    name: k,
    value: v,
    color: labelColorMap[k],
  }));
  const total = data.reduce((acc, curr) => acc + curr.value, 0);

  // Generate Summary
  const topResult = data.sort((a, b) => b.value - a.value)[0];
  const topPercentage = topResult
    ? ((topResult.value / total) * 100).toFixed(1)
    : "0";
  const uniqueLabels = data.length;

  return (
    <div
      className="group relative h-[300px] perspective-1000 animate-in zoom-in-50 fade-in fill-mode-backwards"
      style={{ animationDelay: `${500 + index * 100}ms` }}
      onClick={() => setIsFlipped(!isFlipped)}
    >
      <div
        className={cn(
          "relative w-full h-full transition-all duration-700 ease-in-out transform-style-3d cursor-pointer shadow-xl",
          isFlipped ? "rotate-y-180" : ""
        )}
      >
        {/* FRONT FACE */}
        <Card className="absolute inset-0 backface-hidden bg-card/30 border-white/5 backdrop-blur-md hover:border-primary/40 transition-colors">
          <CardHeader className="pb-2">
            <div className="flex justify-between items-center">
              <CardTitle
                className="text-lg font-medium text-foreground/90 truncate mr-2"
                title={metric}
              >
                {metric}
              </CardTitle>
              <div className="p-2 rounded-full bg-white/5 group-hover:bg-primary/10 transition-colors">
                <BarChart2 className="w-4 h-4 text-muted-foreground group-hover:text-primary" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="h-[180px] w-full mt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data} layout="vertical" margin={{ left: -20 }}>
                  <XAxis type="number" hide />
                  <YAxis
                    dataKey="name"
                    type="category"
                    width={100}
                    tick={{ fill: "#94a3b8", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    content={<CustomTooltip />}
                    cursor={{ fill: "rgba(255,255,255,0.05)", radius: 4 }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                    {data.map((entry, idx) => (
                      <Cell key={`cell-${idx}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-4 pt-4 border-t border-white/5 flex justify-between items-center text-sm">
              <span className="text-muted-foreground">Total Evaluated</span>
              <span className="font-mono font-bold text-foreground">
                {total}
              </span>
            </div>
            <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] text-muted-foreground bg-black/50 px-2 py-1 rounded pointer-events-none">
              Click to flip
            </div>
          </CardContent>
        </Card>

        {/* BACK FACE */}
        <Card className="absolute inset-0 backface-hidden rotate-y-180 bg-gradient-to-br from-gray-900 to-black border-primary/20 flex flex-col justify-center items-center text-center p-6">
          <div className="mb-4 p-3 bg-primary/10 rounded-full">
            <Activity className="w-8 h-8 text-primary" />
          </div>
          <h4 className="text-lg font-bold text-primary mb-2">Summary</h4>
          <p className="text-sm text-muted-foreground mb-4">
            Analysis for <span className="text-foreground">{metric}</span>
          </p>

          <div className="grid grid-cols-2 gap-4 w-full text-left">
            <div className="bg-white/5 p-3 rounded-lg">
              <p className="text-[10px] text-muted-foreground uppercase">Top Result</p>
              <p className="text-sm font-bold text-foreground truncate" title={topResult?.name}>{topResult?.name || "N/A"}</p>
            </div>
            <div className="bg-white/5 p-3 rounded-lg">
              <p className="text-[10px] text-muted-foreground uppercase">Dominance</p>
              <p className="text-sm font-bold text-foreground">{topPercentage}%</p>
            </div>
            <div className="bg-white/5 p-3 rounded-lg">
              <p className="text-[10px] text-muted-foreground uppercase">Variety</p>
              <p className="text-sm font-bold text-foreground">{uniqueLabels} labels</p>
            </div>
            <div className="bg-white/5 p-3 rounded-lg">
              <p className="text-[10px] text-muted-foreground uppercase">Count</p>
              <p className="text-sm font-bold text-foreground">{total}</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

// Reusable Metric Card Component with "Big Number" aesthetics
const StatCard = ({
  title,
  value,
  subtext,
  icon: Icon,
  trend,
  color = "text-primary",
  delay = 0,
}: {
  title: string;
  value: string | number;
  subtext?: string;
  icon: any;
  trend?: string;
  color?: string;
  delay?: number;
}) => (
  <Card
    className="relative overflow-hidden border-white/5 bg-gradient-to-br from-card to-card/50 hover:to-white/5 transition-all duration-500 group animate-in zoom-in-95 fade-in fill-mode-both"
    style={{ animationDelay: `${delay}ms` }}
  >
    <div
      className={cn(
        "absolute -right-6 -top-6 w-32 h-32 rounded-full blur-3xl opacity-20 transition-opacity group-hover:opacity-40",
        color.replace("text-", "bg-")
      )}
    />
    <CardContent className="p-6">
      <div className="flex justify-between items-start mb-4">
        <div
          className={cn(
            "p-3 rounded-xl bg-white/5 border border-white/5 backdrop-blur-md",
            color
          )}
        >
          <Icon className="w-6 h-6" />
        </div>
        {trend && (
          <span className="text-xs font-medium px-2 py-1 rounded-full bg-success/10 text-success border border-success/20">
            {trend}
          </span>
        )}
      </div>
      <div>
        <p className="text-muted-foreground text-sm font-medium tracking-wide uppercase mb-1">
          {title}
        </p>
        <h3 className="text-4xl font-bold tracking-tight text-foreground">
          {value}
        </h3>
        {subtext && (
          <p className="text-xs text-muted-foreground mt-2 font-light">
            {subtext}
          </p>
        )}
      </div>
    </CardContent>
  </Card>
);

/**
 * ------------------------------------------------------------------
 * MAIN COMPONENT
 * ------------------------------------------------------------------
 */
const RAGOutput: React.FC = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { id } = useParams();
  const { getChatbot } = useChatbots();
  const location = useLocation();

  const chatbot = id ? getChatbot(id as string) : null;
  const apiResponse = (location.state as any)?.evaluationResponse;

  if (!chatbot)
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <Activity className="w-12 h-12 text-muted-foreground mx-auto animate-pulse" />
          <h1 className="text-2xl font-semibold text-foreground">
            Chatbot context missing
          </h1>
          <Button onClick={() => navigate("/")}>Go Home</Button>
        </div>
      </div>
    );

  if (!apiResponse)
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <FileJson className="w-12 h-12 text-muted-foreground mx-auto" />
          <h1 className="text-2xl font-semibold text-foreground">
            No evaluation data found
          </h1>
          <p className="text-muted-foreground">
            Please run an evaluation first.
          </p>
          <Button onClick={() => navigate(`/evaluation`)}>
            Go to Evaluation
          </Button>
        </div>
      </div>
    );

  /* --------------------------------------------------------
       DATA PROCESSING
       -------------------------------------------------------- */
  const metrics: string[] =
    apiResponse.metrics || Object.keys(apiResponse.results || {});

  const perMetricCounts: Record<string, Record<string, number>> = {};
  const globalCounts: Record<string, number> = {};
  let totalRecords = 0;

  metrics.forEach((metric) => {
    const metricData = apiResponse.results[metric];
    const results = metricData?.results || [];
    const counts: Record<string, number> = {};

    results.forEach((r: any) => {
      const val = r.label;
      if (val && String(val).toLowerCase() !== "unknown") {
        counts[val] = (counts[val] || 0) + 1;
        globalCounts[val] = (globalCounts[val] || 0) + 1;
      }
    });

    perMetricCounts[metric] = counts;
    totalRecords += metricData?.total_records || results.length || 0;
  });

  // Calculate Aggregates
  const totalLabels = Object.values(globalCounts).reduce((a, b) => a + b, 0);
  const mostCommonLabel = Object.entries(globalCounts).sort(
    (a, b) => b[1] - a[1]
  )[0];

  const factualCount = globalCounts["factual"] || 0;
  const factualRate = totalLabels
    ? ((factualCount / totalLabels) * 100).toFixed(1)
    : "0";

  // Data for Charts
  const overallBarData = metrics.map((metric) => {
    const counts = perMetricCounts[metric];
    return {
      name: metric,
      ...counts,
    };
  });

  const allUniqueLabels = Array.from(new Set(Object.keys(globalCounts)));

  // Assign colors to labels for consistency across all charts
  const labelColorMap: Record<string, string> = {};
  allUniqueLabels.forEach((lbl, idx) => {
    labelColorMap[lbl] = CHART_PALETTE[idx % CHART_PALETTE.length];
  });

  /* --------------------------------------------------------
       EXPORTS
       -------------------------------------------------------- */
  const exportJSON = () => {
    saveAs(
      new Blob(
        [
          JSON.stringify(
            { meta: apiResponse, results: apiResponse.results },
            null,
            2
          ),
        ],
        { type: "application/json" }
      ),
      `${chatbot.name}_evaluation.json`
    );
    toast({ title: "JSON Exported Successfully" });
  };

  const exportCSV = () => {
    const rows: string[] = ["metric,label,value"];
    metrics.forEach((metric) => {
      Object.entries(perMetricCounts[metric]).forEach(([lbl, val]) => {
        rows.push(`${metric},${lbl},${val}`);
      });
    });
    saveAs(
      new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8;" }),
      `${chatbot.name}_evaluation.csv`
    );
    toast({ title: "CSV Exported Successfully" });
  };

  return (
    <div className="min-h-screen bg-background text-foreground animate-in fade-in duration-700">
      {/* BACKGROUND ELEMENTS */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 -left-64 w-[600px] h-[600px] bg-primary/5 rounded-full blur-[100px]" />
        <div className="absolute bottom-0 -right-64 w-[600px] h-[600px] bg-secondary/5 rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10 flex flex-col min-h-screen">
        {/* HEADER */}
        <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border/50 supports-[backdrop-filter]:bg-background/60">
          <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate(`/evaluation-selection/${id}`)}
                className="hover:bg-primary/10 hover:text-primary transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </Button>
              <div className="flex flex-col">
                <h1 className="text-xl font-bold text-foreground tracking-tight">
                  {chatbot.name}
                </h1>
                <span className="text-xs text-muted-foreground">
                  Evaluation Report
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={exportCSV}
                className="hidden sm:flex border-border/50 hover:border-primary/50 text-xs gap-2"
              >
                <BarChart2 className="w-3.5 h-3.5" />
                Export CSV
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={exportJSON}
                className="hidden sm:flex border-border/50 hover:border-secondary/50 text-xs gap-2"
              >
                <FileText className="w-3.5 h-3.5" />
                Export JSON
              </Button>
              <RecordsTableModal
                apiResponse={apiResponse}
                chatbotName={chatbot.name}
              />
              <Button
                variant="default"
                size="sm"
                onClick={() => navigate("/evaluation")}
                className="bg-primary text-primary-foreground hover:bg-primary/90 shadow-lg shadow-primary/20 text-xs"
              >
                Done
              </Button>
            </div>
          </div>
        </header>

        {/* MAIN CONTENT */}
        <main className="flex-1 max-w-[1600px] mx-auto w-full p-6 space-y-8">

          {/* 1. TOP STATS GRID */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              title="Overall Accuracy"
              value={`${factualRate}%`}
              subtext="Based on factual consistency"
              icon={Target}
              color="text-primary"
              trend={Number(factualRate) > 80 ? "Excellent" : "Needs Review"}
              delay={100}
            />
            <StatCard
              title="Total Records"
              value={totalRecords}
              subtext="Across all metrics"
              icon={Layers}
              color="text-secondary"
              delay={200}
            />
            <StatCard
              title="Evaluated Metrics"
              value={metrics.length}
              subtext="Distinct evaluation criteria"
              icon={Activity}
              color="text-warning"
              delay={300}
            />
            <StatCard
              title="Dominant Outcome"
              value={mostCommonLabel ? mostCommonLabel[0] : "N/A"}
              subtext={`${mostCommonLabel ? mostCommonLabel[1] : 0} occurrences`}
              icon={CheckCircle2}
              color="text-success"
              delay={400}
            />
          </div>

          {/* 2. OVERALL DISTRIBUTION CHART */}
          <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in slide-in-from-bottom-5 duration-700 delay-300 fill-mode-backwards">
            {/* Left: Stacked Bar */}
            <Card className="lg:col-span-2 bg-black/20 border-white/5 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart2 className="w-5 h-5 text-primary" />
                  Metric Distribution
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[350px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={overallBarData}
                      margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="rgba(255,255,255,0.05)"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="name"
                        stroke="#94a3b8"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis
                        stroke="#94a3b8"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.05)" }} />
                      <Legend
                        wrapperStyle={{ paddingTop: "20px" }}
                        iconType="circle"
                      />
                      {allUniqueLabels.map((lbl) => (
                        <Bar
                          key={lbl}
                          dataKey={lbl}
                          stackId="a"
                          fill={labelColorMap[lbl]}
                          radius={[0, 0, 0, 0]}
                          maxBarSize={60}
                          animationDuration={1500}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Right: Global Pie */}
            <Card className="bg-black/20 border-white/5 backdrop-blur-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <PieChartIcon className="w-5 h-5 text-secondary" />
                  Overall Outcomes
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-center justify-center">
                <div className="h-[300px] w-full relative">
                  {/* Center Text Overlay */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-3xl font-bold text-foreground">{totalRecords}</span>
                    <span className="text-xs text-muted-foreground uppercase tracking-widest">Total</span>
                  </div>
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={Object.entries(globalCounts).map(([k, v]) => ({
                          name: k,
                          value: v,
                        }))}
                        innerRadius={80}
                        outerRadius={110}
                        paddingAngle={5}
                        dataKey="value"
                        stroke="none"
                      >
                        {Object.keys(globalCounts).map((key, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={labelColorMap[key] || COLORS.neutral}
                          />
                        ))}
                      </Pie>
                      <Tooltip content={<CustomTooltip />} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                {/* Custom Legend */}
                <div className="flex flex-wrap justify-center gap-3 mt-4">
                  {Object.entries(globalCounts).map(([key, value]) => (
                    <div key={key} className="flex items-center gap-1.5 text-xs">
                      <span className="w-2 h-2 rounded-full" style={{ background: labelColorMap[key] }} />
                      <span className="text-muted-foreground">{key}</span>
                      <span className="font-mono text-foreground font-medium">{value}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </section>

          {/* 3. DETAILED METRIC BREAKDOWN */}
          <section className="space-y-6">
            <h2 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-white/60 animate-in fade-in slide-in-from-left-4 duration-700 delay-500">
              Metric Breakdown
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {metrics.map((metric, idx) => (
                <MetricFlipCard
                  key={metric}
                  metric={metric}
                  counts={perMetricCounts[metric]}
                  labelColorMap={labelColorMap}
                  index={idx}
                />
              ))}
            </div>
          </section>

        </main>
      </div>

      <Outlet />
    </div>
  );
};

export default RAGOutput;