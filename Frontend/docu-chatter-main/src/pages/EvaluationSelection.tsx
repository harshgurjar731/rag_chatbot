import { FiTrash2 } from "react-icons/fi";
import { SingleValue } from "react-select";
import SelectMulti from "react-select";
import { CardDescription } from '@/components/ui/card';
import { Trash2, Upload, Plus, FileText, MessageSquarePlus, Settings } from 'lucide-react';
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
import { useState, useEffect, useRef } from "react";
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
  const { getChatbot, deleteChatbot, addDocument, addQnA, } = useChatbots();
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
  const [generatedQA, setGeneratedQA] = useState<
    { question: string; answer: string; file_id: number; question_id: number; datastore_id: number }[]
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

  // ✅ Call the hook once at the top level
  const { config } = useConfigOptions();

  // ✅ Safely extract frameworks
  // 1️⃣ Get the full eval_framworks object
  const evalFrameworksObj = config?.eval_framworks || {};

  // 2️⃣ Extract the framework names (keys)
  const frameworks = Object.keys(evalFrameworksObj);

  // 3️⃣ Extract metrics per framework (values)
  const frameworkMetrics: { [framework: string]: string[] } = {};
  frameworks.forEach((fw) => {
    frameworkMetrics[fw] = evalFrameworksObj[fw];
  });

  console.log("Available Frameworks:", frameworks);

  const handleAutomationFlow = async (datastoreId: number) => {
    setLoading(true);
    try {
      const response = await axios.get(`${config?.base_url}/evaluation/datastore/${datastoreId}`);
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
      setSelectedDocs([]);
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
            `${config?.base_url}/datastores/${chatbot.datastoreId}/files/${encodeURIComponent(docName)}/id`
          );
          fileId = idRes.data.file_id;
        }
      }

      const response = await fetch(
        `${config?.base_url}/evaluation/datastore/${chatbot.datastoreId}/qna`,
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

  const getFileName = async (file_id: number): Promise<string> => {
    try {
      const res = await fetch(`${config.base_url}/datastores/${chatbot.datastoreId}/files/${file_id}/name`);
      if (!res.ok) throw new Error("File not found");
      const data = await res.json();
      return data.file_name; // assuming API returns { filename: "..." }
    } catch {
      return "Unknown File";
    }
  };
  useEffect(() => {
    const fetchFileNames = async () => {
      const names: { [key: number]: string } = {};
      for (const qa of generatedQA) {
        names[qa.file_id] = await getFileName(qa.file_id);
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
      // 1️⃣ Get question_id from API
      const questionIdResponse = await fetch(
        `${config.base_url}/evaluation/datastore/qna/id?file_id=${file_id}&question=${encodeURIComponent(
          question
        )}`
      );
      if (!questionIdResponse.ok) throw new Error("Failed to get question ID");

      const { question_id } = await questionIdResponse.json();

      // 2️⃣ Delete QA by question_id
      const deleteResponse = await fetch(`${config.base_url}/evaluation/datastore/qna/${question_id}`, {
        method: "DELETE",
      });
      if (!deleteResponse.ok) throw new Error("Failed to delete QA");

      // 3️⃣ Update frontend state
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
      minHeight: "2.5rem", // allows growth
      width: "66.666667%", // md:w-2/3
      borderRadius: "calc(var(--radius) - 2px)",
      borderWidth: "1px",
      borderColor: state.menuIsOpen
        ? "hsl(var(--ring))"
        : state.isFocused
          ? "hsl(var(--ring))"
          : "hsl(var(--input))",
      backgroundColor: "hsl(var(--background))",
      padding: "0.25rem 0.75rem",
      fontSize: "0.875rem", // text-sm
      lineHeight: "1.25rem",
      color: "#ffffff", // text color white
      boxShadow: state.isFocused
        ? "0 0 0 2px hsl(var(--ring) / 0.5)"
        : "none",
      transition: "all 0.2s ease-in-out",
      cursor: state.isDisabled ? "not-allowed" : "pointer",
      opacity: state.isDisabled ? 0.5 : 1,
      flexWrap: "wrap", // ✅ allows multiValue items to wrap and expand height
    }),

    menu: (base) => ({
      ...base,
      zIndex: 50,
      fontSize: "0.875rem",
      borderRadius: "var(--radius)",
      marginTop: "0.25rem",
      backgroundColor: "hsl(var(--popover))",
      color: "hsl(var(--popover-foreground))",
      border: "1px solid hsl(var(--border))",
      boxShadow: "0 8px 32px -8px hsl(195 100% 50% / 0.15)", // fallback for var(--shadow-card)
      width: "66.666667%", // match control width
      position: "absolute",
    }),

    option: (base, { isFocused, isSelected }) => ({
      ...base,
      borderRadius: "calc(var(--radius) - 2px)",
      margin: "2px 4px",
      padding: "0.5rem 0.75rem",
      backgroundColor: isSelected
        ? "hsl(var(--primary))"
        : isFocused
          ? "hsl(var(--muted))"
          : "transparent",
      color: isSelected
        ? "hsl(var(--primary-foreground))"
        : "hsl(var(--foreground))",
      cursor: "pointer",
      transition: "all 0.15s ease-in-out",
    }),

    multiValue: (base) => ({
      ...base,
      backgroundColor: "hsl(var(--muted))",
      borderRadius: "calc(var(--radius) - 2px)",
      padding: "4px 8px",
      margin: "2px",
      transition: "all 0.2s ease", // smooth growth/shrink
    }),
    multiValueLabel: (base) => ({
      ...base,
      color: "hsl(var(--muted-foreground))",
      fontWeight: 500,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap",
    }),
    multiValueRemove: (base) => ({
      ...base,
      color: "hsl(var(--muted-foreground))",
      borderRadius: "0.25rem",
      cursor: "pointer",
      ":hover": {
        backgroundColor: "hsl(var(--destructive))",
        color: "hsl(var(--destructive-foreground))",
      },
    }),
    placeholder: (base) => ({
      ...base,
      color: "hsl(var(--muted-foreground))",
      fontSize: "0.875rem",
    }),
    singleValue: (base) => ({
      ...base,
      color: "hsl(var(--foreground))",
    }),
    dropdownIndicator: (base, state) => ({
      ...base,
      color: "hsl(var(--muted-foreground))",
      transition: "transform 0.2s ease",
      transform: state.selectProps.menuIsOpen ? "rotate(180deg)" : "rotate(0deg)",
      ":hover": {
        color: "hsl(var(--foreground))",
      },
    }),
    indicatorSeparator: () => ({
      display: "none",
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
    console.log("✅ Final evaluation results stored:", result);
    toast({ title: "Evaluation Completed", description: "Results are ready!" });
  };

  const startEvaluationApi = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${config?.base_url}/evaluation/start-evaluation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          datastore_id: chatbot.datastoreId,
          datastore_name: chatbot.name,
          framework: selectedFramework,
          metrics: selectedMetrics,
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

  const [evaluationId, setEvaluationId] = useState<string | null>(null);

  // --- Step Status Helper ---
  const getStepStatus = (index: number) => {
    if (index < currentStep) return "completed";
    if (index === currentStep) return "current";
    return "pending";
  };

  // --- Handle start evaluation ---
  const handleStartEvaluation = async () => {
    try {
      setEvaluationStarted(true);

      // call backend to start evaluation
      const startRes = await startEvaluationApi();
      if (!startRes?.evaluation_id) return;

      // save ID for polling
      setEvaluationId(startRes.evaluation_id);

      // reset UI
      setIsCompleted(false);
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
          `${config?.base_url}/evaluation/evaluation-status/${evaluationId}`
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
            // setEvaluationResult(data.results);
            // ✅ Flatten results for UI
            // const flattenedResults = Object.entries(data.results || {}).flatMap(
            //   ([metric, metricData]: [string, any]) =>
            //     (metricData.results || []).map((r: any) => ({
            //       metric,
            //       ...r,
            //     }))
            // );

            // // store in state
            // setEvaluationResult(flattenedResults);

            // // notify parent with clean data
            // onEvaluationComplete(flattenedResults);


            toast({
              title: "Evaluation Completed",
              description: "Results are ready!",
            });
            // ✅ fire callback only when done
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
          {/* <h1 className="text-2xl font-bold text-foreground mb-4">Chatbot Not Found</h1> */}
          {/* <Button onClick={() => navigate('/')} variant="chatbot">
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Button> */}
          <div className="animate-pulse space-y-4">
            <div className="h-6 w-48 bg-muted rounded"></div>
            <div className="h-10 w-40 bg-muted rounded"></div>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="min-h-screen bg-gradient-surface">
      <header className="border-b border-chatbot-primary/20 bg-gradient-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-4 ">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/evaluation")}
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-3xl font-bold text-foreground">{chatbot.name} Evaluation </h1>
            </div>
          </div>
        </div>
      </header>

      {/* <main className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8"> */}
      {/* min-h-screen bg-gradient-surface */}
      <div className="min-h-screen w-full bg-gradient-surface from-indigo-50 via-white to-white px-6 py-12">
        <Tabs defaultValue="evaluation" className="space-y-6">
          <TabsList className="grid w-full grid-cols-2  bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 p-1">
            <TabsTrigger value="evaluation" className="flex items-center gap-2">
              <MessageSquarePlus className="h-4 w-4" />
              Evaluation
            </TabsTrigger>
            <TabsTrigger value="datacuration" className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Data Curation
            </TabsTrigger>
          </TabsList>
          <TabsContent value="evaluation" className="space-y-4">
            <div className="max-w-full mx-auto space-y-16">
              <Card className="shadow-md rounded-2xl border border-gray-10">
                <CardHeader>
                  <CardTitle className=" text-2xl font-bold text-black-800 ">
                    Configure Evaluation Parameters
                  </CardTitle>
                </CardHeader>

                <CardContent className="space-y-8">
                  {/* Framework Selection */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700">Select Framework</label>
                    <Select
                      value={selectedFramework || ""}
                      onValueChange={(value) => {
                        setSelectedFramework(value);
                        // Reset selected metrics when framework changes
                        setSelectedMetrics([]);
                      }}
                      disabled={evaluationStarted}
                    >
                      <SelectTrigger className="w-full md:w-2/3">
                        <SelectValue placeholder="Choose evaluation framework" />
                      </SelectTrigger>

                      <SelectContent>
                        {frameworks.map((framework) => (
                          <SelectItem key={framework} value={framework}>
                            {framework}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Metrics Selection */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700">Select Evaluator Metrics</label>
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
                      placeholder="Select Evaluator metrics"
                      isDisabled={!selectedFramework || evaluationStarted}
                    />
                  </div>

                  {/* Start Evaluation Button */}
                  {/* <Button
    onClick={handleStartEvaluation}
    disabled={
      !selectedFramework || selectedMetrics.length === 0 || evaluationStarted || loading
    }
    className={`w-full md:w-2/3 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 
text-white shadow-lg transition-opacity flex items-center justify-center py-3 text-base rounded-xl
${loading ? "opacity-70 cursor-not-allowed" : "hover:opacity-90"}`}
  >
    {loading ? (
      <>
        <svg
          className="animate-spin h-5 w-5 mr-2 text-white"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          ></circle>
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
          ></path>
        </svg>
        Starting...
      </>
    ) : (
      <>
        <Play className="h-5 w-5 mr-2" />
        Start Evaluation
      </>
    )}
  </Button> */}

                  <Button
                    onClick={() => {
                      if (!selectedFramework) {
                        toast({
                          title: "Framework not selected",
                          description: "Please select a framework before starting evaluation.",
                          variant: "destructive",
                        });
                        return;
                      }

                      if (selectedMetrics.length === 0) {
                        toast({
                          title: "Metrics not selected",
                          description: "Please select at least one metric.",
                          variant: "destructive",
                        });
                        return;
                      }

                      // ✅ Safe to proceed
                      handleStartEvaluation();
                    }}
                    disabled={loading || evaluationStarted}
                    className={`w-full md:w-2/3 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 
text-white shadow-lg flex items-center justify-center py-3 rounded-xl 
${loading ? "opacity-70 cursor-not-allowed" : "hover:opacity-90"}`}
                  >
                    {loading ? (
                      <span>Starting...</span>
                    ) : (
                      <>
                        <Play className="h-5 w-5 mr-2" />
                        Start Evaluation
                      </>
                    )}
                  </Button>
                </CardContent>

              </Card>

              {/* Evaluation Timeline */}
              {evaluationStarted && (
                <Card
                  ref={timelineRef}
                  className="w-full shadow-md rounded-2xl border border-gray-10"
                >
                  {/* Header */}
                  <CardHeader className="px-6 pt-6 pb-4">
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between">
                      <CardTitle className="text-xl font-semibold text-gray-10">
                        Processing Timeline
                      </CardTitle>
                      <p className="text-sm text-gray-500 mt-2 md:mt-0">{timelineStatus}</p>
                    </div>
                  </CardHeader>

                  {/* Timeline */}
                  <CardContent className="px-6 pb-8 space-y-8">
                    <div className="flex items-center justify-between w-full overflow-x-auto py-4 gap-8 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent">
                      {timelineSteps.map((step, index) => (
                        <div
                          key={index}
                          className="timeline-step flex-shrink-0 transition-all duration-500 ease-out"
                          style={{
                            opacity: visibleSteps.includes(index) ? 1 : 0,
                            transform: visibleSteps.includes(index)
                              ? "translateY(0)"
                              : "translateY(40px)",
                          }}
                        >
                          <TimelineStep
                            label={step}
                            status={getStepStatus(index)}
                            isLast={index === timelineSteps.length - 1}
                          />
                        </div>
                      ))}
                    </div>

                    {/* CTA Button */}
                    <div className="flex justify-center">
                      <Button
                        onClick={() => {
                          if (evaluationResult) {
                            const framework = evaluationResult?.framework?.toLowerCase();
                            const targetPath =
                              framework === "ragaas"
                                ? `/ragaas-output/${chatbot.id}`
                                : `/rag-output/${chatbot.id}`;

                            navigate(targetPath, {
                              state: { evaluationResponse: evaluationResult },
                            });
                          }
                        }}
                        disabled={!isCompleted}
                        className="w-full md:w-2/3 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 
    text-white shadow-lg hover:opacity-90 transition-opacity disabled:opacity-50 
    flex items-center justify-center py-3 text-base rounded-xl"
                      >
                        <Eye className="h-5 w-5 mr-2" />
                        Show Result
                      </Button>

                    </div>
                  </CardContent>
                </Card>
              )}

            </div>
          </TabsContent>
          <TabsContent value="datacuration" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Current Q&As */}
              <Card>

                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MessageSquarePlus className="h-5 w-5" />
                    Q&A Pairs ({chatbot.qna.length})
                  </CardTitle>
                  <CardDescription>
                    Custom question and answer pairs for this chatbot
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!generatedQA || generatedQA.length === 0 ? (
                    <p className="text-muted-foreground text-center py-8">
                      No Q&A pairs generated yet
                    </p>
                  ) : (
                    <div className="space-y-4 max-h-96 overflow-y-auto">
                      {generatedQA.map((qa, index) => (
                        <div
                          key={index}
                          className="relative p-4 rounded-xl border border-gray-200 bg-white shadow-sm hover:shadow-md transition"
                        >
                          {/* Delete Icon */}
                          <FiTrash2
                            className="absolute top-2 right-2 text-red-500 hover:text-red-700 cursor-pointer"
                            size={18}
                            onClick={async () => {
                              if (!confirm("Are you sure you want to delete this QA?")) return;

                              try {
                                // Call API to delete QA
                                await deleteQA(qa.file_id, qa.question);

                                // Remove from UI
                                setGeneratedQA((prev) =>
                                  prev.filter((item) => item.question_id !== qa.question_id)
                                );
                              } catch (err) {
                                console.error("Failed to delete QA:", err);
                                alert("Failed to delete QA. Try again.");
                              }
                            }}
                            title="Delete QA"
                          />

                          {/* File Name */}
                          <div className="text-xs font-medium text-gray-500 mb-1">
                            File: {fileNames[qa.file_id]}
                          </div>

                          {/* Question */}
                          <div className="flex items-start space-x-2">
                            <span className="px-2 py-1 text-xs font-semibold text-white bg-blue-500 rounded">
                              Q
                            </span>
                            <p className="text-sm text-gray-800">{qa.question}</p>
                          </div>

                          {/* Answer */}
                          <div className="flex items-start space-x-2 mt-3">
                            <span className="px-2 py-1 text-xs font-semibold text-white bg-green-500 rounded">
                              A
                            </span>
                            <p className="text-sm text-gray-600">{qa.answer}</p>
                          </div>
                        </div>
                      ))}
                    </div>

                  )}
                </CardContent>

              </Card>

              {/* Add New Q&A */}
              <Card>
                {/* <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Plus className="h-5 w-5" />
                    Add Q&A Pair
                  </CardTitle>
                  <CardDescription>
                    Add custom question and answer pairs
                  </CardDescription>
                </CardHeader> */}
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <MessageSquarePlus className="h-5 w-5" />
                    Select Data Curation Method
                  </CardTitle>
                  <CardDescription>
                    select method for data curation for this chatbot out of the following choices.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Step 1: Selection for Curation Type */}
                  <div>
                    <Label>Data Curation Mode</Label>
                    <div className="mt-2 flex space-x-4">
                      <Button
                        type="button"
                        variant={curationMode === "automation" ? "chatbot" : "outline"}
                        onClick={() => setCurationMode("automation")}
                      >
                        Automation
                      </Button>
                      <Button
                        type="button"
                        variant={curationMode === "manual" ? "chatbot" : "outline"}
                        onClick={() => setCurationMode("manual")}
                      >
                        Manual
                      </Button>
                    </div>
                  </div>

                  {/* Step 2: Automation Flow */}
                  {curationMode === "automation" && (
                    <div className="space-y-4">
                      <Button
                        className="w-full"
                        variant="chatbot"
                        onClick={() => handleAutomationFlow(chatbot.datastoreId)}
                        disabled={loading}
                      >
                        {loading ? "Processing..." : "Run Automation"}
                      </Button>


                      {/* Display generated Q&A in side panel after completion */}
                      {/* {generatedQA && (
                        <div className="border rounded-lg p-4 bg-gray-50">
                          <h3 className="font-semibold text-sm mb-2">Generated Q&A</h3>
                          <ul className="space-y-2">
                            {generatedQA.map((item, idx) => (
                              <li key={idx} className="text-sm">
                                <span className="font-medium">Q:</span> {item.question}
                                <br />
                                <span className="font-medium">A:</span> {item.answer}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )} */}
                    </div>
                  )}

                  {/* Step 3: Manual Flow */}
                  {curationMode === "manual" && (
                    <div className="space-y-4">
                      {/* File Upload */}
                      <div>
                        <Label htmlFor="file">Select File</Label>
                        <SelectMulti
                          isMulti={false}
                          styles={customMultiStyles}
                          options={getChatbotDocumentOptions(chatbot)}
                          value={selectedDocs}  // Only the first selected item
                          onChange={(selected: DocumentOption | null) =>
                            setSelectedDocs(selected ? [selected] : [])
                          }
                          isDisabled={isLoading}
                          placeholder="Choose document"
                        />
                      </div>

                      {/* Question */}
                      <div>
                        <Label htmlFor="question">Question</Label>
                        <Input
                          id="question"
                          placeholder="Enter a question..."
                          value={newQuestion}
                          onChange={(e) => setNewQuestion(e.target.value)}
                          className="mt-1.5"
                        />
                      </div>

                      {/* Answer */}
                      <div>
                        <Label htmlFor="answer">Answer</Label>
                        <Textarea
                          id="answer"
                          placeholder="Enter the answer..."
                          value={newAnswer}
                          onChange={(e) => setNewAnswer(e.target.value)}
                          className="mt-1.5 min-h-[100px]"
                        />
                      </div>

                      {/* Submit */}
                      <Button
                        variant="chatbot"
                        className="w-full"
                        onClick={handleManualSubmit}
                        disabled={!newQuestion.trim() || !newAnswer.trim() || selectedDocs.length === 0 || isLoading}
                      >
                        Submit Q&A
                      </Button>
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