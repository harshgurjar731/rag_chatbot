import { FiTrash2 } from "react-icons/fi";
import { SingleValue } from "react-select";
import SelectMulti from "react-select";
import { CardDescription } from '@/components/ui/card';
import { Trash2, Upload, Plus, FileText, MessageSquarePlus, Settings, Loader2, Database, BrainCircuit, CheckCircle, Sparkles } from 'lucide-react';
import { API_BASE_URL } from '@/constants';
// Define rich step info mapping
const STEP_INFO = [
  { label: "Initializing", desc: "Setting up environment", icon: Loader2 },
  { label: "Fetching Data", desc: "Retrieving context & Q&A", icon: Database },
  { label: "Running Evaluation", desc: "Calculating  metrics", icon: BrainCircuit },
  { label: "Finalizing", desc: "Formatting results", icon: Sparkles },
];
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useParams } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ChatInterface } from '@/components/ChatInterface';
import { useChatbots } from '@/hooks/useChatbots';
import { useToast } from '@/hooks/use-toast';
import { Trash } from "lucide-react"; // Make sure Trash icon is imported
import axios from 'axios';
import qs from "qs";
import { useState, useEffect, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TimelineStep } from "@/components/TimelineStep";
import { ArrowLeft, Play, Eye } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { get } from 'http';
import { Outlet } from "react-router-dom";
import gsap from "gsap";

import { useConfigOptions } from "@/hooks/useConfigOptions"


import { ScrollTrigger } from "gsap/ScrollTrigger";


gsap.registerPlugin(ScrollTrigger);


const timelineSteps = [
  "Document Uploaded",
  "Document Chunked",
  "Indexing Completed",
  "Embedding Completed"
];

interface DocumentOption {
  label: string;
  value: string;
}

const EvaluationSelection = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [selectedMetric, setSelectedMetric] = useState("");
  const [currentStep, setCurrentStep] = useState(0);
  const { getChatbot, deleteChatbot } = useChatbots();
  const { toast } = useToast();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [newFile, setNewFile] = useState<File | null>(null);
  const { chatbots, setChatbots } = useChatbots();
  const { refetchChatbots } = useChatbots();


  const [isDragging, setIsDragging] = useState(false);
  const chatbot = id ? getChatbot(id) : null;
  console.log("Selected Chatbot ID:", id);
  console.log("Chatbot Details:", chatbots);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const [curationMode, setCurationMode] = useState<"automation" | "manual" | null>("automation");
  const [loading, setLoading] = useState(false);
  const [generatingQA, isGeneratingQA] = useState(false);
  const [generatedQA, setGeneratedQA] = useState<
    { question: string; answer: string; file_id: number; document_id?: number; question_id: number; datastore_id: number }[]
  >([]);


  const [newQuestion, setNewQuestion] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const [selectedFramework, setSelectedFramework] = useState<string | null>(null);
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
  const [selectedEvaluator, setSelectedEvaluator] = useState<string | null>(null);
  const [evaluationStarted, setEvaluationStarted] = useState(false);
  const [timelineSteps, setTimelineSteps] = useState<string[]>([]);
  const [isCompleted, setIsCompleted] = useState(false);

  const [timelineStatus, setTimelineStatus] = useState("");
  const [progress, setProgress] = useState(0);

  // Cache state
  const [cachedEvaluation, setCachedEvaluation] = useState<any>(null);
  const [checkingCache, setCheckingCache] = useState(false);

  // ✅ Call the hook once at the top level
  const { config } = useConfigOptions();

  // Γ£à Safely extract frameworks
  // 1∩╕ÅΓâú Get the full eval_framworks object
  const evalFrameworksObj = config?.eval_framworks || {};

  // 2∩╕ÅΓâú Extract the framework names (keys)
  const frameworks = Object.keys(evalFrameworksObj);

  // 3∩╕ÅΓâú Extract metrics per framework (values)
  const frameworkMetrics: { [framework: string]: string[] } = {};
  frameworks.forEach((fw) => {
    frameworkMetrics[fw] = evalFrameworksObj[fw];
  });

  console.log("Available Frameworks:", frameworks);

  const fetchGeneratedQA = async (datastoreId: number) => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/evaluation/datastore/${datastoreId}`);
      // Ensure response.data is an array
      const qaData = Array.isArray(response.data) ? response.data : [];
      setGeneratedQA(qaData);
      console.log("Generated Q&A:", qaData);
    } catch (error) {
      console.error(error);
      setGeneratedQA([]);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateQA = async () => {
    isGeneratingQA(true);
    try {
      const response = await fetch(`${API_BASE_URL}/evaluation/generate-qa/${chatbot.datastoreId}`);
      if (!response.ok) throw new Error("Failed to start Q&A generation");
      const data = await response.json();

      const qaEvaluationId = data.evaluation_id;

      toast({
        title: "Q&A Generation Started",
        description: "Generation is running in the background. Polling for completion...",
      });
      console.log("Q&A Generation Response:", data);

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_BASE_URL}/evaluation/evaluation-status/${qaEvaluationId}`);
          if (!statusRes.ok) {
            clearInterval(pollInterval);
            isGeneratingQA(false);
            return;
          }

          const statusData = await statusRes.json();
          console.log("Q&A Generation Status:", statusData);

          if (statusData.status === "completed") {
            clearInterval(pollInterval);
            await fetchGeneratedQA(chatbot.datastoreId);
            isGeneratingQA(false);
            toast({
              title: "Q&A Generation Complete",
              description: `Generated ${statusData.results?.qa_count || 0} Q&A pairs`,
            });
          } else if (statusData.status === "failed") {
            clearInterval(pollInterval);
            isGeneratingQA(false);
            toast({
              title: "Q&A Generation Failed",
              description: statusData.error || "Unknown error",
              variant: "destructive",
            });
          }
          // Continue polling if status is pending, generating_qa, etc.
        } catch (pollError) {
          console.error("Error polling Q&A status:", pollError);
          clearInterval(pollInterval);
          isGeneratingQA(false);
        }
      }, 3000); // Poll every 3 seconds

    } catch (error) {
      console.error("Error generating Q&A:", error);
      toast({
        title: "Error",
        description: "Failed to start Q&A generation",
        variant: "destructive",
      });
      isGeneratingQA(false);
    }
  };

  const [isLoading, setIsLoading] = useState(false);
  // Get evaluation result from state
  const [evaluationResult, setEvaluationResult] = useState<any>(null);

  const [selectedDocs, setSelectedDocs] = useState<DocumentOption[]>([]);
  const [documentOptions, setDocumentOptions] = useState<DocumentOption[]>([]);

  const handleRemove = (value: string) => {
    setSelectedDocs((prevDocs) => prevDocs.filter((doc) => doc.value !== value));
  };

  // Automatically update options when chatbot documents change
  useEffect(() => {
    if (!chatbot?.documents) {
      setDocumentOptions([]);
      return;
    }

    const newOptions = getChatbotDocumentOptions(chatbot);
    setDocumentOptions(newOptions);
  }, [chatbot?.documents]);

  useEffect(() => {
    if (!chatbot?.documents) {
      // If chatbot or documents is undefined, reset selectedDocs
      if (selectedDocs.length > 0) {
        setSelectedDocs([]);
      }
      return;
    }

    const updatedOptions = getChatbotDocumentOptions(chatbot);
    const updatedSelected = selectedDocs.filter((doc) =>
      updatedOptions.some((opt) => opt.value === doc.value)
    );

    if (updatedSelected.length !== selectedDocs.length) {
      setSelectedDocs(updatedSelected);
    }
  }, [chatbot?.documents, selectedDocs]);

  // Fetch Q&A pairs when component mounts or chatbot changes
  useEffect(() => {
    if (chatbot?.datastoreId) {
      fetchGeneratedQA(chatbot.datastoreId);
    }
  }, [chatbot?.datastoreId]);

  // Check for cached evaluation when framework and chatbot are ready
  const checkCachedEvaluation = useCallback(async () => {
    if (!selectedFramework || !chatbot?.datastoreId) return;

    setCheckingCache(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/evaluation/check-cache/${chatbot.datastoreId}?framework=${selectedFramework}&chatbot_id=${chatbot.id}`
      );
      if (!response.ok) throw new Error("Failed to check cache");

      const data = await response.json();
      if (data.has_cache) {
        setCachedEvaluation(data);
        console.log("Found cached evaluation:", data);
      } else {
        setCachedEvaluation(null);
      }
    } catch (error) {
      console.error("Error checking cache:", error);
      setCachedEvaluation(null);
    } finally {
      setCheckingCache(false);
    }
  }, [selectedFramework, chatbot?.datastoreId, chatbot?.id]);

  // Check cache when framework or chatbot changes
  useEffect(() => {
    checkCachedEvaluation();
  }, [checkCachedEvaluation]);





  const getChatbotDocumentOptions = (chatbot: { documents?: string[] }): DocumentOption[] => {
    if (!chatbot?.documents || chatbot.documents.length === 0) return [];

    return chatbot.documents.map((doc) => ({
      label: doc,
      value: doc,
    }));
  };

  // Manual handler with API call
  const handleManualSubmit = async () => {
    if (!selectedDocs.length) {
      alert("Please select a document.");
      return;
    }

    setIsLoading(true);


    let fileId = -1;
    try {

      if (selectedDocs.length > 0) {

        for (const doc of selectedDocs) {
          const docName = doc.label;
          const idRes = await axios.get<{ file_id: number }>(
            `${API_BASE_URL}/ingestion/datastore/${chatbot.datastoreId}/files/${encodeURIComponent(docName)}/id`
          );
          fileId = idRes.data.file_id;
        }
      }

      const response = await fetch(
        `${API_BASE_URL}/evaluation/datastore/${chatbot.datastoreId}/qna`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            file_id: fileId, // ensure it's a number
            question: newQuestion,
            answer: newAnswer,
          }),
        }
      );
      if (!response.ok) {
        throw new Error("Failed to save Q&A");
      }

      const data = await response.json();
      console.log("Q&A saved:", data);

      // Construct full Q&A object for state
      const qaData = [
        {
          question: newQuestion,
          answer: newAnswer,
          file_id: fileId,
          question_id: Date.now(), // temporary unique id for frontend
          datastore_id: chatbot.datastoreId,
        },
      ];

      setGeneratedQA((prev) => [...prev, ...qaData]);
      console.log("Generated Q&A:", qaData);


      // Reset fields
      setSelectedDocs([]);
      setNewQuestion("");
      setNewAnswer("");
    } catch (error) {
      console.error("Error saving Q&A:", error);
      alert("Failed to save Q&A. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };;
  const [fileNames, setFileNames] = useState<{ [key: number]: string }>({});

  const getFileName = async (file_id?: number, document_id?: number): Promise<string> => {
    try {
      let url = "";
      if (document_id) {
        url = `${API_BASE_URL}/ingestion/datastore/${chatbot.datastoreId}/documents/${document_id}/name`;
      } else if (file_id) {
        url = `${API_BASE_URL}/ingestion/datastore/${chatbot.datastoreId}/files/${file_id}/name`;
      } else {
        return "Unknown File";
      }

      const res = await fetch(url);
      if (!res.ok) throw new Error("File not found");
      const data = await res.json();
      return data.file_name;
    } catch {
      return "Unknown File";
    }
  };
  useEffect(() => {
    const fetchFileNames = async () => {
      const names: { [key: number]: string } = {};
      for (const qa of generatedQA) {
        // Use document_id as key preference, fallback to file_id (though file_id might be null)
        // Actually, we should store by the ID we use.
        // Let's store by index or just map both if needed.
        // Simplest: use document_id if available.
        const id = qa.document_id || qa.file_id;
        if (id) {
          names[id] = await getFileName(qa.file_id, qa.document_id);
        }
      }
      setFileNames(names);
    };

    if (generatedQA.length > 0) {
      fetchFileNames();
    }
  }, [generatedQA]);


  // Delete QA by question text and file_id
  const deleteQA = async (file_id: number, question: string) => {
    try {
      // 1∩╕ÅΓâú Get question_id from API
      const questionIdResponse = await fetch(
        `${API_BASE_URL}/evaluation/datastore/qna/id?file_id=${file_id}&question=${encodeURIComponent(
          question
        )}`
      );
      if (!questionIdResponse.ok) throw new Error("Failed to get question ID");

      const { question_id } = await questionIdResponse.json();

      // 2∩╕ÅΓâú Delete QA by question_id
      const deleteResponse = await fetch(`${API_BASE_URL}/evaluation/datastore/qna/${question_id}`, {
        method: "DELETE",
      });
      if (!deleteResponse.ok) throw new Error("Failed to delete QA");

      // 3∩╕ÅΓâú Update frontend state
      setGeneratedQA((prev) => prev.filter((item) => item.question_id !== question_id));
      alert("QA deleted successfully");
    } catch (err) {
      console.error(err);
      alert("Error deleting QA");
    }
  };

  const customMultiStyles = {
    control: (base, state) => ({
      ...base,
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      minHeight: "3rem", // Match h-12
      width: "100%",
      borderRadius: "0.75rem", // rounded-xl
      borderWidth: "1px",
      borderColor: state.isFocused ? "rgb(99 102 241)" : "rgba(255, 255, 255, 0.1)", // indigo-500 or white/10
      backgroundColor: "rgba(255, 255, 255, 0.05)", // white/5
      padding: "0.25rem 0.5rem",
      fontSize: "0.875rem",
      color: "#f3f4f6", // gray-100
      boxShadow: state.isFocused ? "0 0 0 1px rgb(99 102 241)" : "none",
      transition: "all 0.2s ease-in-out",
      cursor: "pointer",
      ":hover": {
        borderColor: "rgba(255, 255, 255, 0.2)",
      },
    }),

    menu: (base) => ({
      ...base,
      zIndex: 9999, // Ensure it sits on top
      borderRadius: "0.75rem",
      marginTop: "0.5rem",
      backgroundColor: "#111827", // gray-900 (Solid color for readability)
      border: "1px solid rgba(255, 255, 255, 0.1)",
      boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)",
      overflow: "hidden",
    }),

    option: (base, { isFocused, isSelected }) => ({
      ...base,
      backgroundColor: isSelected
        ? "rgb(79 70 229)" // indigo-600
        : isFocused
          ? "rgba(255, 255, 255, 0.1)" // Hover state
          : "transparent",
      color: isSelected ? "white" : "#e5e7eb", // gray-200
      cursor: "pointer",
      padding: "0.75rem 1rem",
    }),

    multiValue: (base) => ({
      ...base,
      backgroundColor: "rgba(99, 102, 241, 0.2)", // indigo-500/20
      border: "1px solid rgba(99, 102, 241, 0.3)",
      borderRadius: "0.375rem",
    }),
    multiValueLabel: (base) => ({
      ...base,
      color: "#e0e7ff", // indigo-100
      fontWeight: 500,
    }),
    multiValueRemove: (base) => ({
      ...base,
      color: "#a5b4fc", // indigo-300
      ":hover": {
        backgroundColor: "rgba(99, 102, 241, 0.4)",
        color: "white",
      },
    }),
    input: (base) => ({
      ...base,
      color: "white",
    }),
    placeholder: (base) => ({
      ...base,
      color: "#9ca3af", // gray-400
    }),
    singleValue: (base) => ({
      ...base,
      color: "#f3f4f6",
    }),
    dropdownIndicator: (base) => ({
      ...base,
      color: "#9ca3af",
      ":hover": { color: "white" },
    }),
    menuPortal: (base) => ({
      ...base,
      zIndex: 9999,
    }),
  };

  // State to track which timeline steps have appeared
  const [visibleSteps, setVisibleSteps] = useState<number[]>([]);

  useEffect(() => {
    if (timelineSteps.length > 0) {
      timelineRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

      // Animate each step with stagger
      timelineSteps.forEach((_, index) => {
        setTimeout(() => {
          setVisibleSteps((prev) => [...prev, index]);
        }, index * 250); // 250ms stagger
      });
    }
  }, [timelineSteps]);

  const onEvaluationComplete = (result: any) => {
    setEvaluationResult(result);
    console.log("Γ£à Final evaluation results stored:", result);
    toast({ title: "Evaluation Completed", description: "Results are ready!" });
  };

  const startEvaluationApi = async (forceRerun: boolean = false) => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/evaluation/start-evaluation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          datastore_id: chatbot.datastoreId,
          datastore_name: chatbot.name,
          framework: selectedFramework,
          metrics: selectedMetrics,
          chatbot_id: chatbot.id,
          force_rerun: forceRerun,
        }),
      });

      if (!response.ok) throw new Error("Failed to start evaluation");
      return await response.json();
    } catch (err) {
      console.error("Error starting evaluation:", err);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // View cached results
  const handleViewCachedResults = async () => {
    if (!cachedEvaluation?.evaluation_id) return;

    try {
      setLoading(true);
      const response = await fetch(
        `${API_BASE_URL}/evaluation/cached-results/${cachedEvaluation.evaluation_id}`
      );
      if (!response.ok) throw new Error("Failed to fetch cached results");

      const data = await response.json();

      // Flatten results for UI (same format as live evaluation)
      const flattenedResults = Object.entries(data.results || {}).flatMap(
        ([metric, metricData]: [string, any]) =>
          (Array.isArray(metricData) ? metricData : metricData.results || []).map((r: any) => ({
            metric,
            ...r,
          }))
      );

      setEvaluationResult(flattenedResults);
      setIsCompleted(true);
      setEvaluationStarted(true);

      toast({
        title: "Cached Results Loaded",
        description: `Loaded evaluation from ${new Date(data.created_at).toLocaleDateString()}`,
      });
    } catch (error) {
      console.error("Error loading cached results:", error);
      toast({
        title: "Error",
        description: "Failed to load cached results",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const [evaluationId, setEvaluationId] = useState<string | null>(null);

  // --- Step Status Helper ---
  const getStepStatus = (index: number) => {
    if (index < currentStep) return "completed";
    if (index === currentStep) return "current";
    return "pending";
  };

  // --- Handle start evaluation ---
  const handleStartEvaluation = async (forceRerun: boolean = false) => {
    try {
      setEvaluationStarted(true);
      setCachedEvaluation(null); // Clear cache when starting new evaluation

      // call backend to start evaluation
      const startRes = await startEvaluationApi(forceRerun);
      if (!startRes?.evaluation_id) return;

      // save ID for polling
      setEvaluationId(startRes.evaluation_id);

      // reset UI
      setIsCompleted(false);
      setEvaluationResult(null);
      setTimelineSteps([
        "Initializing",
        "Fetching Data",
        "Running Evaluation",
        "Generating Report",
      ]);
      setCurrentStep(0);
      setProgress(0);
      setTimelineStatus("Initializing...");
    } catch (err) {
      console.error("Failed to start evaluation:", err);
      setTimelineStatus("Error");
      setEvaluationStarted(false);
    }
  };

  // --- Polling useEffect ---
  useEffect(() => {
    if (!evaluationId) return;

    let pollInterval: NodeJS.Timeout;

    const pollEvaluation = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/evaluation/evaluation-status/${evaluationId}`
        );
        if (!res.ok) throw new Error("Failed to fetch evaluation status");
        const data = await res.json();

        let stepIndex = 0;
        let statusMessage = "";

        switch (data.status) {
          case "initializing":
            stepIndex = 0;
            statusMessage = "Initializing...";
            break;
          case "fetching_data":
            stepIndex = 1;
            statusMessage = "Fetching Data...";
            break;
          case "qa_generated":
          case "running_evaluation":
            stepIndex = 2;
            statusMessage = "Running Evaluation...";
            break;
          case "evaluation_completed":
            stepIndex = 3;
            statusMessage = "Finalizing Results...";
            break;
          case "completed":
            stepIndex = 3;
            statusMessage = "Completed";
            setIsCompleted(true);
            clearInterval(pollInterval);
            // Γ£à Flatten results for UI
            const flattenedResults = Object.entries(data.results || {}).flatMap(
              ([metric, metricData]: [string, any]) =>
                (metricData.results || []).map((r: any) => ({
                  metric,
                  ...r,
                }))
            );

            // store in state
            setEvaluationResult(flattenedResults);

            // notify parent with clean data
            onEvaluationComplete(flattenedResults);


            toast({
              title: "Evaluation Completed",
              description: "Results are ready!",
            });
            // Γ£à fire callback only when done
            onEvaluationComplete(data);
            break;
          case "failed":
            stepIndex = 3;
            statusMessage = "Failed";
            clearInterval(pollInterval);
            setIsCompleted(false);
            break;
          default:
            statusMessage = "Running...";
        }

        // update UI states progressively
        setCurrentStep(stepIndex);
        setTimelineStatus(statusMessage);
        setProgress(data.progress || 0);
      } catch (err) {
        clearInterval(pollInterval);
        setTimelineStatus("Error");
        console.error("Error polling evaluation:", err);
      }
    };

    // immediately call once
    pollEvaluation();
    // then keep polling
    pollInterval = setInterval(pollEvaluation, 2000);

    // cleanup on unmount or new eval
    return () => clearInterval(pollInterval);
  }, [evaluationId]);


  if (!chatbot) {
    return (
      <div className="min-h-screen bg-gradient-surface flex items-center justify-center">
        <div className="text-center">
          <div className="animate-pulse space-y-4">
            <div className="h-6 w-48 bg-muted rounded"></div>
            <div className="h-10 w-40 bg-muted rounded"></div>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen bg-gradient-surface text-gray-100 font-sans selection:bg-indigo-500/30">

      <header className="border-b border-gray-800 bg-gradient-card mb-6 shadow-md">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/evaluation")}
              className="hover:bg-white/10 text-gray-400 hover:text-white rounded-full"
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-xl font-medium tracking-tight text-white flex items-center gap-2">
                <span className="opacity-50">Evaluation /</span>
                {chatbot.name}
              </h1>
            </div>
          </div>
        </div>
      </header>

      <div className="pb-20 px-6 max-w-7xl mx-auto space-y-10 relative z-10">

        {/* Page Title & Desc */}
        <div className="space-y-2">
          <h2 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white via-gray-200 to-gray-400">
            Evaluation Hub
          </h2>
          <p className="text-lg text-gray-500 max-w-2xl">
            Configure evaluation parameters or curate custom Q&A datasets to refine your chatbot's performance.
          </p>
        </div>

        <Tabs defaultValue="evaluation" className="space-y-10">
          <div className="flex justify-start">
            <TabsList className="bg-gray-900/50 border border-white/5 p-1 rounded-full backdrop-blur-sm shadow-xl">
              <TabsTrigger
                value="evaluation"
                className="rounded-full px-6 py-2.5 data-[state=active]:bg-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-lg hover:text-white transition-all text-gray-400 gap-2 flex"
              >
                <MessageSquarePlus className="h-4 w-4" />
                Evaluation
              </TabsTrigger>
              <TabsTrigger
                value="datacuration"
                className="rounded-full px-6 py-2.5 data-[state=active]:bg-indigo-600 data-[state=active]:text-white data-[state=active]:shadow-lg hover:text-white transition-all text-gray-400 gap-2 flex"
              >
                <FileText className="h-4 w-4" />
                Data Curation
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="evaluation" className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Configuration Card */}
              <Card className="lg:col-span-1 border border-white/10 bg-white/5 backdrop-blur-sm shadow-2xl rounded-3xl overflow-hidden">
                <div className="h-1 w-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500" />
                <CardHeader>
                  <CardTitle className=" text-xl font-semibold text-white">
                    Configuration
                  </CardTitle>
                  <CardDescription className="text-gray-400">
                    Set up your evaluation run settings.
                  </CardDescription>
                </CardHeader>

                <CardContent className="space-y-6">
                  <div className="space-y-3">
                    <Label className="text-gray-300 font-medium ml-1">Framework</Label>
                    <Select
                      value={selectedFramework || ""}
                      onValueChange={(value) => {
                        setSelectedFramework(value);
                        setSelectedMetrics([]);
                      }}
                      disabled={evaluationStarted}
                    >
                      <SelectTrigger className="w-full h-12 rounded-xl bg-white/5 border-white/10 text-white focus:ring-indigo-500/50 focus:border-indigo-500">
                        <SelectValue placeholder="Select Framework" />
                      </SelectTrigger>
                      <SelectContent className="bg-gray-900 border-white/10 text-white">
                        {frameworks.map((framework) => (
                          <SelectItem key={framework} value={framework} className="focus:bg-white/10 focus:text-white cursor-pointer">
                            {framework}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-3">
                    <Label className="text-gray-300 font-medium ml-1">Metrics</Label>
                    <SelectMulti
                      isMulti
                      styles={customMultiStyles}
                      options={
                        selectedFramework && evalFrameworksObj[selectedFramework]
                          ? evalFrameworksObj[selectedFramework].map((metric) => ({
                            value: metric,
                            label: metric,
                          }))
                          : []
                      }
                      value={selectedMetrics.map((metric) => ({ value: metric, label: metric }))}
                      onChange={(selectedOptions) =>
                        setSelectedMetrics(selectedOptions.map((opt) => opt.value))
                      }
                      placeholder="Select metrics..."
                      isDisabled={!selectedFramework || evaluationStarted}
                      menuPortalTarget={document.body}
                      menuPosition="fixed"
                    />
                  </div>

                  <div className="pt-4 space-y-3">
                    {checkingCache ? (
                      <div className="flex items-center justify-center py-3 text-gray-400">
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        Checking for cached results...
                      </div>
                    ) : cachedEvaluation ? (
                      // Show "View Results" and "Re-run" buttons when cache exists
                      <>
                        <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                          <div className="flex items-center gap-2 text-sm text-indigo-300">
                            <CheckCircle className="h-4 w-4" />
                            <span>Cached results available from {new Date(cachedEvaluation.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                        <Button
                          onClick={handleViewCachedResults}
                          disabled={loading || evaluationStarted}
                          className="w-full h-12 rounded-xl text-md font-semibold transition-all duration-300 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white shadow-lg hover:shadow-green-500/25 hover:scale-[1.02]"
                        >
                          <div className="flex items-center gap-2">
                            <Eye className="h-4 w-4" />
                            View Cached Results
                          </div>
                        </Button>
                        <Button
                          onClick={() => {
                            if (!selectedFramework) {
                              toast({
                                title: "Framework Required",
                                description: "Please select a framework first.",
                                variant: "destructive",
                              });
                              return;
                            }
                            if (selectedMetrics.length === 0) {
                              toast({
                                title: "Metrics Required",
                                description: "Please select at least one metric.",
                                variant: "destructive",
                              });
                              return;
                            }
                            handleStartEvaluation(true); // force_rerun = true
                          }}
                          disabled={loading || evaluationStarted}
                          variant="outline"
                          className="w-full h-12 rounded-xl text-md font-semibold transition-all duration-300 border-white/10 bg-white/5 hover:bg-white/10 text-white hover:scale-[1.02]"
                        >
                          {loading ? (
                            <div className="flex items-center gap-2">
                              <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                              Starting...
                            </div>
                          ) : (
                            <div className="flex items-center gap-2">
                              <Play className="h-4 w-4" />
                              Re-run Evaluation
                            </div>
                          )}
                        </Button>
                      </>
                    ) : (
                      // Show "Start Evaluation" button when no cache
                      <Button
                        onClick={() => {
                          if (!selectedFramework) {
                            toast({
                              title: "Framework Required",
                              description: "Please select a framework first.",
                              variant: "destructive",
                            });
                            return;
                          }
                          if (selectedMetrics.length === 0) {
                            toast({
                              title: "Metrics Required",
                              description: "Please select at least one metric.",
                              variant: "destructive",
                            });
                            return;
                          }
                          handleStartEvaluation(false);
                        }}
                        disabled={loading || evaluationStarted}
                        className={`w-full h-12 rounded-xl text-md font-semibold font-medium transition-all duration-300 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white shadow-lg hover:shadow-indigo-500/25 ring-0 border-0 
                          ${loading ? "opacity-70" : "hover:scale-[1.02]"}`}
                      >
                        {loading ? (
                          <div className="flex items-center gap-2">
                            <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                            Starting...
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <Play className="h-4 w-4 fill-white" />
                            Start Evaluation
                          </div>
                        )}
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Timeline Card */}
              <div className="lg:col-span-2">
                {evaluationStarted ? (
                  <Card
                    ref={timelineRef}
                    className="h-full border border-white/10 bg-white/5 backdrop-blur-sm shadow-2xl rounded-3xl overflow-hidden relative"
                  >
                    <div className="absolute inset-0 bg-gradient-to-b from-indigo-500/5 to-transparent pointer-events-none" />
                    <CardHeader className="px-8 pt-8">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-xl font-semibold text-white flex items-center gap-3">
                          <div className="p-2 rounded-lg bg-indigo-500/20">
                            <Settings className="w-5 h-5 text-indigo-400" />
                          </div>
                          Live Progress
                        </CardTitle>
                        <Badge variant="outline" className="border-indigo-500/30 text-indigo-300 bg-indigo-500/10 px-3 py-1 rounded-full uppercase tracking-wider text-xs font-semibold">
                          {timelineStatus}
                        </Badge>
                      </div>
                    </CardHeader>

                    <CardContent className="px-8 pb-8 pt-12">
                      <div className="relative">
                        {/* Connecting Line Backdrop */}
                        <div className="absolute top-5 left-0 w-full h-1 bg-white/5 rounded-full overflow-hidden z-0">
                          <div
                            className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-indigo-500 animate-gradient-x transition-all duration-1000 ease-out"
                            style={{ width: `${progress}%` }}
                          />
                        </div>

                        <div className="grid grid-cols-4 relative z-10">
                          {STEP_INFO.map((info, index) => {
                            const status = getStepStatus(index);
                            const isActive = status === 'current';
                            const isCompleted = status === 'completed';
                            const Icon = info.icon;

                            return (
                              <div key={index} className="flex flex-col items-center gap-4 group"
                                style={{
                                  opacity: visibleSteps.includes(index) ? 1 : 0,
                                  transform: visibleSteps.includes(index) ? 'translateY(0)' : 'translateY(20px)',
                                  transition: `all 0.5s ease-out ${index * 0.2}s`
                                }}>

                                {/* Icon Circle */}
                                <div className={`
                                  w-12 h-12 rounded-2xl flex items-center justify-center border transition-all duration-500 z-20 relative
                                  ${isCompleted
                                    ? 'bg-indigo-500 border-indigo-400 shadow-[0_0_25px_rgba(99,102,241,0.6)] text-white'
                                    : isActive
                                      ? 'bg-gray-900 border-indigo-500 shadow-[0_0_30px_rgba(99,102,241,0.4)] text-indigo-400 scale-110'
                                      : 'bg-gray-900/80 border-white/10 text-gray-600'}
                                `}>
                                  {isActive && (
                                    <div className="absolute inset-0 bg-indigo-500/20 rounded-2xl animate-ping" />
                                  )}
                                  <Icon className={`w-5 h-5 ${isActive && index === 0 ? 'animate-spin' : ''}`} />

                                  {isCompleted && (
                                    <div className="absolute -top-1 -right-1 bg-green-500 rounded-full p-0.5 border-2 border-gray-900">
                                      <CheckCircle className="w-3 h-3 text-white" />
                                    </div>
                                  )}
                                </div>

                                {/* Text Content */}
                                <div className="text-center space-y-1">
                                  <h4 className={`text-sm font-semibold transition-colors duration-300 ${isActive ? 'text-white' : isCompleted ? 'text-gray-200' : 'text-gray-600'
                                    }`}>
                                    {info.label}
                                  </h4>
                                  <p className={`text-xs transition-colors duration-300 ${isActive ? 'text-indigo-400' : 'text-gray-600'
                                    }`}>
                                    {info.desc}
                                  </p>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      <div className="mt-12 flex justify-center">
                        <Button
                          onClick={() => {
                            if (evaluationResult) {
                              const framework = evaluationResult?.framework?.toLowerCase();
                              const targetPath =
                                framework === "ragaas"
                                  ? `/ragaas-output/${chatbot.id}?evalId=${evaluationResult.evaluation_id}`
                                  : `/rag-output/${chatbot.id}?evalId=${evaluationResult.evaluation_id}`;

                              navigate(targetPath, {
                                state: { evaluationResponse: evaluationResult },
                              });
                            }
                          }}
                          disabled={!isCompleted}
                          className={`
                            relative group overflow-hidden px-8 h-12 rounded-xl font-semibold transition-all duration-300
                            ${isCompleted
                              ? 'bg-white text-indigo-950 shadow-[0_0_30px_rgba(255,255,255,0.2)] hover:scale-105 hover:shadow-[0_0_40px_rgba(255,255,255,0.3)]'
                              : 'bg-white/5 text-gray-500 cursor-not-allowed opacity-50'}
                          `}
                        >
                          {isCompleted && (
                            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/50 to-transparent -translate-x-full group-hover:animate-shimmer" />
                          )}
                          <div className="flex items-center gap-2 relative z-10">
                            <Eye className="h-5 w-5" />
                            View Detailed Results
                          </div>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="h-full border border-white/5 bg-white/[0.02] rounded-3xl flex flex-col items-center justify-center text-center p-12 border-dashed">
                    <div className="w-20 h-20 bg-gradient-to-tr from-indigo-500/20 to-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-6 animate-pulse">
                      <Play className="w-8 h-8 text-white/20" />
                    </div>
                    <h3 className="text-xl font-medium text-white mb-2">Ready to Evaluate</h3>
                    <p className="text-gray-500 max-w-sm">
                      Select a framework and metric from the configuration panel to begin the evaluation process.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="datacuration" className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Left: Input Form */}
              <Card className="border border-white/10 bg-white/5 backdrop-blur-sm shadow-2xl rounded-3xl overflow-hidden h-fit">
                <CardHeader>
                  <CardTitle className=" text-xl font-semibold text-white flex items-center gap-2">
                    <FileText className="w-5 h-5 text-purple-400" />
                    Curation Method
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="p-1 bg-black/40 rounded-xl inline-flex w-full">
                    <button
                      onClick={() => setCurationMode("automation")}
                      className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 ${curationMode === 'automation' ? 'bg-indigo-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'
                        }`}
                    >
                      Automation
                    </button>
                    <button
                      onClick={() => setCurationMode("manual")}
                      className={`flex-1 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 ${curationMode === 'manual' ? 'bg-indigo-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'
                        }`}
                    >
                      Manual Entry
                    </button>
                  </div>

                  {curationMode === 'automation' ? (
                    <div className="py-8 text-center space-y-6">
                      <div className="bg-indigo-500/10 w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-4 border border-indigo-500/20">
                        <MessageSquarePlus className="w-10 h-10 text-indigo-400" />
                      </div>
                      <div>
                        <h4 className="text-lg font-medium text-white mb-2">Auto-Generate Q&A</h4>
                        <p className="text-sm text-gray-400 max-w-xs mx-auto">
                          Let our AI analyze your documents and generate high-quality question-answer pairs automatically.
                        </p>
                      </div>
                      <Button
                        className="w-full h-12 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg font-medium text-md"
                        onClick={handleGenerateQA}
                        disabled={generatingQA}
                      >
                        {generatingQA ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Generating...
                          </>
                        ) : "Start Automation"}
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-5">
                      <div className="space-y-2">
                        <Label className="text-gray-300 ml-1">Source Document</Label>
                        <SelectMulti
                          isMulti={false}
                          styles={customMultiStyles}
                          options={getChatbotDocumentOptions(chatbot)}
                          value={selectedDocs}
                          onChange={(selected: DocumentOption | null) =>
                            setSelectedDocs(selected ? [selected] : [])
                          }
                          isDisabled={isLoading}
                          placeholder="Select a file..."
                        />
                      </div>

                      <div className="space-y-2">
                        <Label className="text-gray-300 ml-1">Question</Label>
                        <Input
                          placeholder="e.g. What is the return policy?"
                          value={newQuestion}
                          onChange={(e) => setNewQuestion(e.target.value)}
                          className="bg-white/5 border-white/10 text-white placeholder:text-gray-600 h-10 rounded-xl focus:border-indigo-500/50"
                        />
                      </div>

                      <div className="space-y-2">
                        <Label className="text-gray-300 ml-1">Answer</Label>
                        <Textarea
                          placeholder="e.g. Returns are accepted within 30 days..."
                          value={newAnswer}
                          onChange={(e) => setNewAnswer(e.target.value)}
                          className="bg-white/5 border-white/10 text-white placeholder:text-gray-600 min-h-[120px] rounded-xl focus:border-indigo-500/50 resize-none"
                        />
                      </div>

                      <Button
                        className="w-full h-12 rounded-xl bg-white text-black hover:bg-gray-200 font-semibold shadow-lg mt-4"
                        onClick={handleManualSubmit}
                        disabled={!newQuestion.trim() || !newAnswer.trim() || selectedDocs.length === 0 || isLoading}
                      >
                        Save Pair
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Right: Existing Q&A List */}
              <Card className="border border-white/10 bg-white/5 backdrop-blur-sm shadow-2xl rounded-3xl overflow-hidden h-[600px] flex flex-col">
                <CardHeader className="border-b border-white/5 pb-4">
                  <div className="flex justify-between items-center">
                    <CardTitle className="text-xl font-semibold text-white">
                      Generated Pairs
                    </CardTitle>
                    <Badge variant="secondary" className="bg-white/10 text-white border-0">
                      {generatedQA?.length || 0} items
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 overflow-hidden p-0">
                  {!generatedQA || generatedQA.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-gray-500 p-8 text-center opacity-60">
                      <FileText className="w-12 h-12 mb-4 opacity-50" />
                      <p>No Q&A pairs found.</p>
                      <p className="text-sm mt-1">Run automation or add manually.</p>
                    </div>
                  ) : (
                    <div className="h-full overflow-y-auto p-4 space-y-3 custom-scrollbar">
                      {generatedQA.map((qa, index) => (
                        <div key={index} className="group relative bg-[#0a0a0a]/40 border border-white/5 p-5 rounded-2xl hover:border-indigo-500/30 transition-all duration-300 hover:shadow-lg hover:bg-[#0a0a0a]/60">
                          <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
                              onClick={async (e) => {
                                e.stopPropagation();
                                if (!confirm("Are you sure?")) return;
                                await deleteQA(qa.file_id, qa.question);
                              }}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>

                          <div className="flex items-center gap-2 mb-3">
                            <Badge variant="outline" className="border-blue-500/20 text-blue-300 bg-blue-500/10 text-[10px] px-2 py-0.5 rounded-md">Q</Badge>
                            <p className="text-sm font-medium text-gray-200 line-clamp-2 pr-8">{qa.question}</p>
                          </div>
                          <div className="flex items-start gap-2 pl-1">
                            <div className="min-w-[3px] h-full self-stretch bg-gray-700/50 rounded-full" />
                            <p className="text-sm text-gray-400 line-clamp-3 leading-relaxed">
                              {qa.answer}
                            </p>
                          </div>
                          <div className="mt-3 pt-3 border-t border-white/5 flex justify-end">
                            <span className="text-xs text-gray-600 flex items-center gap-1">
                              <FileText className="w-3 h-3" />
                              {fileNames[qa.document_id || qa.file_id] || "Unknown source"}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default EvaluationSelection;
