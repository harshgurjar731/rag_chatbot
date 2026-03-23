import { useState, useRef, useCallback, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
    ChevronDown,
    ChevronUp,
    Upload,
    X,
    Film,
    Mic,
    Eye,
    Sparkles,
    Settings,
    Play,
    CheckCircle,
    Loader2,
    RotateCcw,
    Info,
} from "lucide-react";
import axios from "axios";
import { API_BASE_URL } from "@/constants";

/* ── Pipeline stages for progress display ── */
const STAGES = [
    { id: "upload", icon: Upload, label: "Upload" },
    { id: "ingest", icon: Film, label: "Ingestion" },
    { id: "graph", icon: Settings, label: "Graph" },
];

/* ── Default advanced settings ── */
const INITIAL_ADV = {
    chunk_duration_seconds: 30,
    frames_per_chunk: 5,
    frame_selection: "scene_change",
    scene_change_threshold: 30.0,
    resize_resolution: "1080,1080",
    audio_model: "voxtral-mini-latest",
    sample_rate: 16000,
    diarization: true,
    language: "",
    detector: "yolov8x",
    tracker: "bytetrack",
    confidence_threshold: 0.3,
    som_prompting: true,
    vlm_model: "mistral-large-2512",
    vlm_max_tokens: 4096,
    vlm_temperature: 0.1,
    vlm_frames_per_request: 8,
    caption_prompt: "",
    inter_chunk_delay: 2,
};

/* Section keys for reset */
const SECTION_KEYS: Record<string, string[]> = {
    video: [
        "chunk_duration_seconds",
        "frames_per_chunk",
        "frame_selection",
        "scene_change_threshold",
        "resize_resolution",
    ],
    audio: ["audio_model", "sample_rate", "diarization", "language"],
    cv: ["detector", "tracker", "confidence_threshold", "som_prompting"],
    vlm: [
        "vlm_model",
        "vlm_max_tokens",
        "vlm_temperature",
        "vlm_frames_per_request",
        "caption_prompt",
    ],
    pipeline: ["inter_chunk_delay"],
};

function formatSize(bytes: number) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
}

/* ── Tooltip wrapper ── */
function InfoTip({ text }: { text: string }) {
    return (
        <span className="relative group inline-flex items-center ml-1">
            <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
            <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs bg-popover text-popover-foreground border rounded-md shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none w-56 z-50">
                {text}
            </span>
        </span>
    );
}

/* ── Config row ── */
function CfgRow({
    label,
    info,
    children,
}: {
    label: string;
    info?: string;
    children: React.ReactNode;
}) {
    return (
        <div className="flex items-center justify-between gap-4 py-2">
            <span className="text-sm text-foreground/80 flex items-center">
                {label}
                {info && <InfoTip text={info} />}
            </span>
            <div className="flex-shrink-0">{children}</div>
        </div>
    );
}

/* ── Section header ── */
function SectionHeader({
    icon: Icon,
    title,
    onReset,
    disabled,
}: {
    icon: React.ElementType;
    title: string;
    onReset: () => void;
    disabled?: boolean;
}) {
    return (
        <div className="flex items-center gap-2 pb-2 border-b border-border/50 mb-2">
            <Icon className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold text-foreground">{title}</span>
            {disabled && (
                <Badge variant="outline" className="text-xs opacity-60">
                    Disabled
                </Badge>
            )}
            <button
                className="ml-auto text-xs text-muted-foreground hover:text-primary flex items-center gap-1 transition-colors"
                onClick={onReset}
                type="button"
            >
                <RotateCcw className="h-3 w-3" />
                Reset
            </button>
        </div>
    );
}

/* ════════════════════════════════════════════ */
/* ══ Main Component                       ══ */
/* ════════════════════════════════════════════ */

interface VideoUploadDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    datastoreId?: number;
    onBack?: () => void;
}

export const VideoUploadDialog = ({
    open,
    onOpenChange,
    datastoreId,
    onBack,
}: VideoUploadDialogProps) => {
    const [file, setFile] = useState<File | null>(null);
    const [dragover, setDragover] = useState(false);
    const [streamId, setStreamId] = useState("default");
    const [customClasses, setCustomClasses] = useState("");
    const [opts, setOpts] = useState({
        audio: true,
        cv: true,
        graph: true,
    });
    const [processing, setProcessing] = useState(false);
    const [progress, setProgress] = useState(0);
    const [progressText, setProgressText] = useState("");
    const [stages, setStages] = useState<Record<string, string>>({});
    const [done, setDone] = useState(false);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [adv, setAdv] = useState({ ...INITIAL_ADV });
    const [defaults, setDefaults] = useState({ ...INITIAL_ADV });
    const inputRef = useRef<HTMLInputElement>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Load defaults from backend on mount
    useEffect(() => {
        axios
            .get(`${API_BASE_URL}/ingestion/video/defaults`)
            .then((res) => {
                const d = res.data;
                const loaded = {
                    chunk_duration_seconds: d.chunk_duration_seconds ?? 30,
                    frames_per_chunk: d.frames_per_chunk ?? 5,
                    frame_selection: d.frame_selection ?? "scene_change",
                    scene_change_threshold: d.scene_change_threshold ?? 30.0,
                    resize_resolution: d.resize_resolution
                        ? d.resize_resolution.join(",")
                        : "1080,1080",
                    audio_model: d.audio_model ?? "voxtral-mini-latest",
                    sample_rate: d.sample_rate ?? 16000,
                    diarization: d.diarization ?? true,
                    language: d.language ?? "",
                    detector: d.detector ?? "yolov8x",
                    tracker: d.tracker ?? "bytetrack",
                    confidence_threshold: d.confidence_threshold ?? 0.3,
                    som_prompting: d.som_prompting ?? true,
                    vlm_model: d.vlm_model ?? "mistral-large-2512",
                    vlm_max_tokens: d.vlm_max_tokens ?? 4096,
                    vlm_temperature: d.vlm_temperature ?? 0.1,
                    vlm_frames_per_request: d.vlm_frames_per_request ?? 8,
                    caption_prompt: d.caption_prompt ?? "",
                    inter_chunk_delay: d.inter_chunk_delay ?? 2,
                };
                setAdv(loaded);
                setDefaults(loaded);
            })
            .catch(() => { });
    }, []);

    // Cleanup polling on unmount
    useEffect(() => {
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, []);

    const setA = (key: string, val: any) =>
        setAdv((p) => ({ ...p, [key]: val }));
    const toggleOpt = (key: string) =>
        setOpts((prev) => ({ ...prev, [key]: !prev[key as keyof typeof prev] }));

    const resetSection = (section: string) => {
        setAdv((prev) => {
            const next = { ...prev };
            for (const key of SECTION_KEYS[section]) {
                (next as any)[key] = (defaults as any)[key];
            }
            return next;
        });
    };

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setDragover(false);
        if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
    }, []);

    const removeFile = () => {
        setFile(null);
        setDone(false);
        setProcessing(false);
        setProgress(0);
        setProgressText("");
        setStages({});
        if (inputRef.current) inputRef.current.value = "";
    };

    const startProcessing = async () => {
        if (!file || !datastoreId) return;
        setProcessing(true);
        setDone(false);
        setProgress(5);
        setProgressText("Uploading video...");
        setStages({ upload: "active" });

        try {
            // Build settings payload
            const settingsPayload = {
                stream_id: streamId,
                audio: opts.audio,
                cv: opts.cv,
                graph: opts.graph,
                custom_classes: customClasses.trim() || null,
                ...adv,
            };

            // Upload video + dispatch job
            const formData = new FormData();
            formData.append("file", file);
            formData.append("settings", JSON.stringify(settingsPayload));

            const uploadRes = await axios.post(
                `${API_BASE_URL}/ingestion/datastore/${datastoreId}/upload_video`,
                formData,
                { headers: { "Content-Type": "multipart/form-data" } }
            );

            const jobId = uploadRes.data.job_id;
            setStages({ upload: "done", ingest: "active" });
            setProgress(15);
            setProgressText("Video uploaded. Processing pipeline started...");

            // Poll for status
            pollRef.current = setInterval(async () => {
                try {
                    const st = await axios.get(
                        `${API_BASE_URL}/ingestion/video/status/${jobId}`
                    );
                    const data = st.data;
                    setProgress(data.progress || 0);
                    setProgressText(data.message || "");

                    if (data.stage === "ingesting") {
                        setStages((prev) => ({
                            ...prev,
                            upload: "done",
                            ingest: "active",
                        }));
                    } else if (data.stage === "graph") {
                        setStages((prev) => ({
                            ...prev,
                            upload: "done",
                            ingest: "done",
                            graph: "active",
                        }));
                    } else if (data.stage === "complete") {
                        if (pollRef.current) clearInterval(pollRef.current);
                        setStages({
                            upload: "done",
                            ingest: "done",
                            graph: "done",
                        });
                        setProgress(100);
                        setProgressText(
                            "✅ Pipeline complete! Video chunks are ready for Upsert."
                        );
                        setDone(true);
                    } else if (data.stage === "error") {
                        if (pollRef.current) clearInterval(pollRef.current);
                        setProcessing(false);
                    }
                } catch {
                    /* ignore polling errors */
                }
            }, 2000);
        } catch (err: any) {
            if (pollRef.current) clearInterval(pollRef.current);
            setProgressText(
                "❌ Error: " + (err.response?.data?.detail || err.message)
            );
            setProcessing(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
                <DialogHeader>
                    <div className="flex items-center gap-3">
                        {onBack && (
                            <Button variant="ghost" size="icon" onClick={onBack}>
                                <ChevronDown className="h-4 w-4 rotate-90" />
                            </Button>
                        )}
                        <DialogTitle className="text-2xl flex items-center gap-2">
                            <Film className="h-6 w-6 text-primary" />
                            Upload & Process Video
                        </DialogTitle>
                    </div>
                </DialogHeader>

                <div className="flex-1 overflow-y-auto space-y-4 pr-1">
                    {/* Upload Area */}
                    {!file ? (
                        <div
                            className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${dragover
                                    ? "border-primary bg-primary/10"
                                    : "border-border hover:border-primary/50 hover:bg-muted/30"
                                }`}
                            onClick={() => inputRef.current?.click()}
                            onDrop={handleDrop}
                            onDragOver={(e) => {
                                e.preventDefault();
                                setDragover(true);
                            }}
                            onDragLeave={() => setDragover(false)}
                        >
                            <Upload className="h-12 w-12 text-primary mx-auto mb-3" />
                            <h3 className="text-lg font-semibold text-foreground mb-1">
                                Drag & drop video here
                            </h3>
                            <p className="text-sm text-muted-foreground mb-2">
                                or click to browse files
                            </p>
                            <p className="text-xs text-muted-foreground/60">
                                MP4, MKV, AVI, MOV supported
                            </p>
                            <input
                                ref={inputRef}
                                type="file"
                                accept=".mp4,.mkv,.avi,.mov"
                                hidden
                                onChange={(e) =>
                                    e.target.files?.length && setFile(e.target.files[0])
                                }
                            />
                        </div>
                    ) : (
                        <>
                            {/* File Info */}
                            <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/30 border">
                                <Film className="h-8 w-8 text-primary" />
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium text-sm truncate">{file.name}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {formatSize(file.size)}
                                    </p>
                                </div>
                                {!processing && (
                                    <Button variant="ghost" size="icon" onClick={removeFile}>
                                        <X className="h-4 w-4" />
                                    </Button>
                                )}
                            </div>

                            {/* Options (only shown before processing) */}
                            {!processing && (
                                <>
                                    {/* Basic Options */}
                                    <div className="space-y-3 p-4 rounded-lg border bg-card">
                                        <CfgRow label="Video ID (stream_id)">
                                            <Input
                                                className="w-40 h-8 text-sm"
                                                value={streamId}
                                                onChange={(e) => setStreamId(e.target.value)}
                                            />
                                        </CfgRow>
                                        <CfgRow
                                            label="YOLO Target Classes"
                                            info="Comma-separated. Blank = defaults."
                                        >
                                            <Input
                                                className="w-48 h-8 text-sm"
                                                placeholder="person, vehicle"
                                                value={customClasses}
                                                onChange={(e) => setCustomClasses(e.target.value)}
                                            />
                                        </CfgRow>

                                        <div className="flex flex-wrap gap-3 pt-2">
                                            {[
                                                { key: "audio", label: "Audio Transcription", icon: Mic },
                                                { key: "cv", label: "Object Detection (YOLO)", icon: Eye },
                                                { key: "graph", label: "Build Knowledge Graph", icon: Settings },
                                            ].map(({ key, label, icon: Icon }) => (
                                                <label
                                                    key={key}
                                                    className="flex items-center gap-2 text-sm cursor-pointer select-none"
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={opts[key as keyof typeof opts]}
                                                        onChange={() => toggleOpt(key)}
                                                        className="accent-primary"
                                                    />
                                                    <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                                                    {label}
                                                </label>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Advanced Settings Toggle */}
                                    <button
                                        className="flex items-center gap-2 w-full px-4 py-2.5 rounded-lg border bg-card hover:bg-muted/50 transition-colors text-sm font-medium"
                                        onClick={() => setShowAdvanced((v) => !v)}
                                        type="button"
                                    >
                                        {showAdvanced ? (
                                            <ChevronUp className="h-4 w-4 text-primary" />
                                        ) : (
                                            <ChevronDown className="h-4 w-4 text-primary" />
                                        )}
                                        Advanced Settings
                                        <Badge
                                            variant="outline"
                                            className="ml-auto text-xs"
                                        >
                                            {showAdvanced ? "Hide" : "Show"}
                                        </Badge>
                                    </button>

                                    {/* Advanced Settings Panel */}
                                    {showAdvanced && (
                                        <div className="space-y-4">
                                            {/* Video Processing */}
                                            <div className="p-4 rounded-lg border bg-card">
                                                <SectionHeader
                                                    icon={Film}
                                                    title="Video Processing"
                                                    onReset={() => resetSection("video")}
                                                />
                                                <CfgRow
                                                    label="Chunk Duration (s)"
                                                    info="Duration of each video chunk in seconds."
                                                >
                                                    <Input
                                                        type="number"
                                                        className="w-20 h-8 text-sm"
                                                        min={5}
                                                        max={300}
                                                        value={adv.chunk_duration_seconds}
                                                        onChange={(e) =>
                                                            setA("chunk_duration_seconds", +e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                                <CfgRow
                                                    label="Frames Per Chunk"
                                                    info="Number of frames extracted from each chunk."
                                                >
                                                    <Input
                                                        type="number"
                                                        className="w-20 h-8 text-sm"
                                                        min={1}
                                                        max={30}
                                                        value={adv.frames_per_chunk}
                                                        onChange={(e) =>
                                                            setA("frames_per_chunk", +e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                                <CfgRow
                                                    label="Frame Selection"
                                                    info="How frames are chosen from each chunk."
                                                >
                                                    <select
                                                        className="h-8 rounded-md border bg-background px-2 text-sm"
                                                        value={adv.frame_selection}
                                                        onChange={(e) =>
                                                            setA("frame_selection", e.target.value)
                                                        }
                                                    >
                                                        <option value="scene_change">Scene Change</option>
                                                        <option value="uniform">Uniform</option>
                                                    </select>
                                                </CfgRow>
                                                <CfgRow
                                                    label="Scene Threshold"
                                                    info="Mean pixel difference to trigger a scene cut."
                                                >
                                                    <Input
                                                        type="number"
                                                        className="w-20 h-8 text-sm"
                                                        min={1}
                                                        max={255}
                                                        step={1}
                                                        value={adv.scene_change_threshold}
                                                        onChange={(e) =>
                                                            setA("scene_change_threshold", +e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                                <CfgRow
                                                    label="Resize Resolution"
                                                    info="Frame dimensions sent to VLM."
                                                >
                                                    <select
                                                        className="h-8 rounded-md border bg-background px-2 text-sm"
                                                        value={adv.resize_resolution}
                                                        onChange={(e) =>
                                                            setA("resize_resolution", e.target.value)
                                                        }
                                                    >
                                                        <option value="480,480">480×480</option>
                                                        <option value="720,720">720×720</option>
                                                        <option value="1080,1080">1080×1080</option>
                                                    </select>
                                                </CfgRow>
                                            </div>

                                            {/* Audio Settings */}
                                            <div
                                                className={`p-4 rounded-lg border bg-card ${!opts.audio ? "opacity-50" : ""
                                                    }`}
                                            >
                                                <SectionHeader
                                                    icon={Mic}
                                                    title="Audio Transcription"
                                                    onReset={() => resetSection("audio")}
                                                    disabled={!opts.audio}
                                                />
                                                <CfgRow
                                                    label="Audio Model"
                                                    info="Mistral model for transcription."
                                                >
                                                    <Input
                                                        className="w-44 h-8 text-sm"
                                                        value={adv.audio_model}
                                                        onChange={(e) =>
                                                            setA("audio_model", e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                                <CfgRow
                                                    label="Sample Rate"
                                                    info="Audio sample rate in Hz."
                                                >
                                                    <select
                                                        className="h-8 rounded-md border bg-background px-2 text-sm"
                                                        value={adv.sample_rate}
                                                        onChange={(e) =>
                                                            setA("sample_rate", +e.target.value)
                                                        }
                                                    >
                                                        <option value={8000}>8000</option>
                                                        <option value={16000}>16000</option>
                                                        <option value={22050}>22050</option>
                                                        <option value={44100}>44100</option>
                                                    </select>
                                                </CfgRow>
                                                <CfgRow
                                                    label="Speaker Diarization"
                                                    info="Identify different speakers."
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={adv.diarization}
                                                        onChange={(e) =>
                                                            setA("diarization", e.target.checked)
                                                        }
                                                        className="accent-primary h-4 w-4"
                                                    />
                                                </CfgRow>
                                                <CfgRow
                                                    label="Language"
                                                    info="Force a language (blank = auto-detect)."
                                                >
                                                    <Input
                                                        className="w-24 h-8 text-sm"
                                                        placeholder="auto"
                                                        value={adv.language}
                                                        onChange={(e) =>
                                                            setA("language", e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                            </div>

                                            {/* CV Pipeline */}
                                            <div
                                                className={`p-4 rounded-lg border bg-card ${!opts.cv ? "opacity-50" : ""
                                                    }`}
                                            >
                                                <SectionHeader
                                                    icon={Eye}
                                                    title="Object Detection (CV)"
                                                    onReset={() => resetSection("cv")}
                                                    disabled={!opts.cv}
                                                />
                                                <CfgRow
                                                    label="YOLO Detector"
                                                    info="YOLO model variant."
                                                >
                                                    <select
                                                        className="h-8 rounded-md border bg-background px-2 text-sm"
                                                        value={adv.detector}
                                                        onChange={(e) =>
                                                            setA("detector", e.target.value)
                                                        }
                                                    >
                                                        <option value="yolov8n">YOLOv8n (Nano)</option>
                                                        <option value="yolov8s">YOLOv8s (Small)</option>
                                                        <option value="yolov8m">YOLOv8m (Medium)</option>
                                                        <option value="yolov8l">YOLOv8l (Large)</option>
                                                        <option value="yolov8x">YOLOv8x (XL)</option>
                                                    </select>
                                                </CfgRow>
                                                <CfgRow label="Tracker" info="Object tracking algo.">
                                                    <select
                                                        className="h-8 rounded-md border bg-background px-2 text-sm"
                                                        value={adv.tracker}
                                                        onChange={(e) =>
                                                            setA("tracker", e.target.value)
                                                        }
                                                    >
                                                        <option value="bytetrack">ByteTrack</option>
                                                        <option value="botsort">BoT-SORT</option>
                                                    </select>
                                                </CfgRow>
                                                <CfgRow
                                                    label="Confidence"
                                                    info="Minimum detection confidence (0–1)."
                                                >
                                                    <Input
                                                        type="number"
                                                        className="w-20 h-8 text-sm"
                                                        min={0.05}
                                                        max={0.95}
                                                        step={0.05}
                                                        value={adv.confidence_threshold}
                                                        onChange={(e) =>
                                                            setA("confidence_threshold", +e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                                <CfgRow
                                                    label="SOM Prompting"
                                                    info="Overlay bounding boxes on frames for VLM."
                                                >
                                                    <input
                                                        type="checkbox"
                                                        checked={adv.som_prompting}
                                                        onChange={(e) =>
                                                            setA("som_prompting", e.target.checked)
                                                        }
                                                        className="accent-primary h-4 w-4"
                                                    />
                                                </CfgRow>
                                            </div>

                                            {/* VLM Captioning */}
                                            <div className="p-4 rounded-lg border bg-card">
                                                <SectionHeader
                                                    icon={Sparkles}
                                                    title="VLM Captioning"
                                                    onReset={() => resetSection("vlm")}
                                                />
                                                <CfgRow
                                                    label="VLM Model"
                                                    info="Vision-Language Model for captions."
                                                >
                                                    <select
                                                        className="h-8 rounded-md border bg-background px-2 text-sm"
                                                        value={adv.vlm_model}
                                                        onChange={(e) =>
                                                            setA("vlm_model", e.target.value)
                                                        }
                                                    >
                                                        <option value="mistral-large-2512">
                                                            mistral-large-2512
                                                        </option>
                                                        <option value="mistral-medium-2508">
                                                            mistral-medium-2508
                                                        </option>
                                                        <option value="pixtral-large-2501">
                                                            pixtral-large-2501
                                                        </option>
                                                    </select>
                                                </CfgRow>
                                                <CfgRow label="Max Tokens" info="Max output tokens.">
                                                    <Input
                                                        type="number"
                                                        className="w-24 h-8 text-sm"
                                                        min={256}
                                                        max={8192}
                                                        step={256}
                                                        value={adv.vlm_max_tokens}
                                                        onChange={(e) =>
                                                            setA("vlm_max_tokens", +e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                                <CfgRow
                                                    label="Temperature"
                                                    info="Controls randomness (0–1)."
                                                >
                                                    <Input
                                                        type="number"
                                                        className="w-20 h-8 text-sm"
                                                        min={0}
                                                        max={1}
                                                        step={0.05}
                                                        value={adv.vlm_temperature}
                                                        onChange={(e) =>
                                                            setA("vlm_temperature", +e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                                <CfgRow
                                                    label="Frames / Request"
                                                    info="Frames per VLM API call."
                                                >
                                                    <Input
                                                        type="number"
                                                        className="w-20 h-8 text-sm"
                                                        min={1}
                                                        max={16}
                                                        value={adv.vlm_frames_per_request}
                                                        onChange={(e) =>
                                                            setA("vlm_frames_per_request", +e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                                <div className="pt-2">
                                                    <Label className="text-sm text-foreground/80">
                                                        Caption Prompt
                                                    </Label>
                                                    <textarea
                                                        className="mt-1 w-full h-20 rounded-md border bg-background px-3 py-2 text-sm resize-none"
                                                        value={adv.caption_prompt}
                                                        onChange={(e) =>
                                                            setA("caption_prompt", e.target.value)
                                                        }
                                                        placeholder="Default prompt used if blank"
                                                    />
                                                </div>
                                            </div>

                                            {/* Pipeline Settings */}
                                            <div className="p-4 rounded-lg border bg-card">
                                                <SectionHeader
                                                    icon={Settings}
                                                    title="Pipeline"
                                                    onReset={() => resetSection("pipeline")}
                                                />
                                                <CfgRow
                                                    label="Inter-Chunk Delay (s)"
                                                    info="Seconds between chunk processing. Increase if hitting API rate limits."
                                                >
                                                    <Input
                                                        type="number"
                                                        className="w-20 h-8 text-sm"
                                                        min={0}
                                                        max={60}
                                                        step={0.5}
                                                        value={adv.inter_chunk_delay}
                                                        onChange={(e) =>
                                                            setA("inter_chunk_delay", +e.target.value)
                                                        }
                                                    />
                                                </CfgRow>
                                            </div>
                                        </div>
                                    )}

                                    {/* Process Button */}
                                    <Button
                                        size="lg"
                                        className="w-full"
                                        onClick={startProcessing}
                                    >
                                        <Play className="h-4 w-4 mr-2" />
                                        Start Processing
                                    </Button>
                                </>
                            )}

                            {/* Processing / Done States */}
                            {processing && !done && (
                                <Button size="lg" className="w-full" disabled>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Processing...
                                </Button>
                            )}
                            {done && (
                                <Button
                                    size="lg"
                                    className="w-full bg-green-600 hover:bg-green-700 text-white"
                                    disabled
                                >
                                    <CheckCircle className="h-4 w-4 mr-2" />
                                    Complete!
                                </Button>
                            )}
                        </>
                    )}

                    {/* Progress Section */}
                    {processing && (
                        <div className="p-4 rounded-lg border bg-card space-y-3">
                            <h3 className="text-sm font-semibold">Pipeline Progress</h3>
                            {/* Progress Bar */}
                            <div className="h-2 rounded-full bg-muted overflow-hidden">
                                <div
                                    className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-all duration-500"
                                    style={{ width: `${progress}%` }}
                                />
                            </div>
                            <p className="text-sm text-muted-foreground">
                                {progressText || "Starting..."}
                            </p>
                            {/* Stage Indicators */}
                            <div className="flex items-center justify-between gap-2">
                                {STAGES.map((stage, i) => {
                                    const Icon = stage.icon;
                                    const status = stages[stage.id] || "";
                                    return (
                                        <div
                                            key={stage.id}
                                            className="flex flex-col items-center gap-1 flex-1"
                                        >
                                            <div
                                                className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all ${status === "done"
                                                        ? "border-green-500 bg-green-500/10 text-green-500"
                                                        : status === "active"
                                                            ? "border-primary bg-primary/10 text-primary animate-pulse"
                                                            : "border-border bg-muted/30 text-muted-foreground"
                                                    }`}
                                            >
                                                {status === "done" ? (
                                                    <CheckCircle className="h-5 w-5" />
                                                ) : status === "active" ? (
                                                    <Loader2 className="h-5 w-5 animate-spin" />
                                                ) : (
                                                    <Icon className="h-5 w-5" />
                                                )}
                                            </div>
                                            <span className="text-xs text-muted-foreground">
                                                {stage.label}
                                            </span>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </div>

                <DialogFooter className="pt-4 border-t">
                    {done ? (
                        <Button
                            variant="outline"
                            onClick={() => {
                                removeFile();
                                onOpenChange(false);
                            }}
                        >
                            Close
                        </Button>
                    ) : (
                        <Button variant="outline" onClick={() => onOpenChange(false)}>
                            {processing ? "Close (processing continues)" : "Cancel"}
                        </Button>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
