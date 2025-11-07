import { useState, useRef, useEffect } from "react";
import {
  Send,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Chatbot, ChatMessage } from "@/types/chatbot";
import { useToast } from "@/hooks/use-toast";
import { Label } from "@/components/ui/label";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Slider } from "@/components/ui/slider";
import { Info } from "lucide-react";
import { X } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Loader2 } from "lucide-react";
import React from "react";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import SelectMulti from "react-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import axios from "axios";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useConfigOptions } from "@/hooks/useConfigOptions";

interface Citation {
  source: string;
  page?: string | number;
  content?: string;
}


interface QueryPayload {
  question: string;
  fileId: number[];
  optimizer: string;
  embeddingModel: string;
  llmModel: string;
  vectorDb: string;
  temperature: number;
  guardrailOption: string;
  tokenSize: number;
  showSources: boolean;
  rerankerOption: string;
}


interface ChatInterfaceProps {
  chatbot: Chatbot;
  chatbotName: string;
  onSendMessage: (payload: QueryPayload) => Promise<string>;
}


type DocumentOption = {
  label: string;
  value: string;
};


declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
  interface SpeechRecognitionEvent extends Event {
    results: SpeechRecognitionResultList;
  }
}


export const ChatInterface = ({
  chatbot,
  chatbotName,
  onSendMessage,
}: ChatInterfaceProps) => {
  const { config, loading } = useConfigOptions();
  const storageKey = `chat_history_${chatbot?.id}`;
  type StoredChatMessage = Omit<ChatMessage, "timestamp"> & {
    timestamp: string;
  };


  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      try {
        const parsed: StoredChatMessage[] = JSON.parse(saved);
        return parsed.map((msg) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
          traceId: msg.traceId || "",
          Citation: msg.Citation || [],
        }));
      } catch (err) {
        console.error("Failed to parse saved messages:", err);
        return [];
      }
    }
    return [
      {
        id: "1",
        content: `Hello, I am your ${chatbot.name}. How can I help you today?`,
        isUser: false,
        timestamp: new Date(),
        traceId: "-1",
        Citation: [],
      },
    ];
  });


  function getFilenameFromPath(fullPath: string): string {
    if (!fullPath) {
      return "";
    }


    // 1. Normalize slashes: Replace all backslashes (\) with forward slashes (/).
    const normalizedPath = fullPath.replace(/\\/g, "/");


    // 2. Find the last index of the forward slash.
    const lastSlashIndex = normalizedPath.lastIndexOf("/");


    // 3. Extract the substring starting right after the last slash.
    // If no slash is found (e.g., just "file.txt"), slice returns the whole string.
    return normalizedPath.substring(lastSlashIndex + 1);
  }


  useEffect(() => {
    const toStore: StoredChatMessage[] = messages.map((msg) => ({
      ...msg,
      timestamp: msg.timestamp.toISOString(),
    }));
    localStorage.setItem(storageKey, JSON.stringify(toStore));
  }, [messages]);


  const [openDropdownId, setOpenDropdownId] = useState<string | null>(null);


  const toggleLanguageDropdown = (id: string) => {
    setOpenDropdownId(openDropdownId === id ? null : id);
  };


  const handleTranslate = async (
    id: string,
    text: string,
    targetLang: string
  ): Promise<void> => {
    try {
      const res = await fetch(`${config?.base_url}/translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          q: text,
          source: "auto",
          target: targetLang,
          format: "text",
        }),
      });


      if (!res.ok) throw new Error("Translation API failed");
      const data: { translatedText: string } = await res.json();


      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === id
            ? {
                ...msg,
                originalContent: msg.originalContent || msg.content,
                content: data.translatedText,
              }
            : msg
        )
      );
      setOpenDropdownId(null);
    } catch (err) {
      console.error("Translation failed:", err);
    }
  };


  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();
  const [tokenSize, setTokenSize] = useState(256);
  const [showSources, setShowSources] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openPopoverId, setOpenPopoverId] = useState<string | null>(null);


  const getChatbotDocumentOptions = (chatbot: {
    documents?: string[];
  }): DocumentOption[] => {
    if (!chatbot?.documents || chatbot.documents.length === 0) return [];
    return chatbot.documents.map((doc) => ({
      label: doc,
      value: doc,
    }));
  };


  const scrapeWebsite = async (datastoreId: number, url: string) => {
    try {
      const { data } = await axios.post(
        `${config?.base_url}/urlscraper/${datastoreId}`,
        {},
        { params: { url } }
      );
      return data;
    } catch (err: any) {
      console.error(
        "Error scraping website:",
        err.response?.data || err.message
      );
      throw err;
    }
  };


  const handleUrlSubmit = async () => {
    if (!urlInput.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await scrapeWebsite(chatbot.datastoreId, urlInput);
      console.log("Scrape success:", result);
      toast({
        title: "Website processed successfully 🎉",
        description:
          "Please refresh the page and select the scraped URL file from the 'Select Documents' option.",
        duration: 10000,
      });
      setUrlInput("");
      return result;
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };


  const getFormattedLabel = (filename: string): string => {
    const nameWithoutExt = filename.replace(/\.[^/.]+$/, "");
    return nameWithoutExt
      .replace(/[_\-]/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };


  const [selectedDocs, setSelectedDocs] = useState<DocumentOption[]>([]);
  const [documentOptions, setDocumentOptions] = useState<DocumentOption[]>([]);


  const handleRemove = (value: string) => {
    setSelectedDocs((prevDocs) =>
      prevDocs.filter((doc) => doc.value !== value)
    );
  };


  useEffect(() => {
    const newOptions = getChatbotDocumentOptions(chatbot);
    setDocumentOptions(newOptions);
  }, [chatbot.documents]);


  useEffect(() => {
    const updatedOptions = getChatbotDocumentOptions(chatbot);
    const updatedSelected = selectedDocs.filter((doc) =>
      updatedOptions.some((opt) => opt.value === doc.value)
    );
    if (updatedSelected.length !== selectedDocs.length) {
      setSelectedDocs(updatedSelected);
    }
  }, [chatbot?.documents]);


  useEffect(() => {
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector(
        "[data-radix-scroll-area-viewport]"
      );
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [messages]);


  // Define this function inside your ChatInterface component
  const handleFileClick = async (
    e: React.MouseEvent<HTMLAnchorElement>,
    datastoreId: number,
    filename: string,
    // ✅ NEW: Accept pageNumber, assuming the citation passes the first page
    pageNumber?: string | number
  ) => {
    // Prevent the default navigation of the anchor tag (href="#")
    e.preventDefault();


    try {
      // 1. Fetch the file content as a blob
      const response = await axios.get(
        // Assuming config?.base_url is available in scope.
        `${config?.base_url}/datastores/${datastoreId}/files/${filename}`,
        {
          responseType: "blob",
        }
      );


      // 2. Create a Blob URL
      const contentType = response.headers["content-type"];
      const blob = new Blob([response.data], { type: contentType });
      let blobUrl = window.URL.createObjectURL(blob);


      // 3. ✅ DEEP LINK LOGIC: Redirect to a specific page if pageNumber is provided
      if (pageNumber && contentType === "application/pdf") {
        const pageNum = parseInt(String(pageNumber), 10);
        if (!isNaN(pageNum) && pageNum > 0) {
          // Append the standard PDF fragment identifier for page redirection
          // The browser will handle the redirect once the PDF loads in the new window
          blobUrl = `${blobUrl}#page=${pageNum}`;
        }
      }


      // 4. Open in a new window
      window.open(blobUrl, "_blank");


      // Clean up the URL object after opening (optional but good practice)
      window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error("Error opening document:", error);
      // Use toast instead of alert()
      toast({
        title: "Error Opening File",
        description:
          "Failed to download and open the document. Please ensure the backend is running.",
        variant: "destructive",
      });
    }
  };


  const handleTokenSizeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    if (!isNaN(value)) {
      const clampedValue = Math.min(Math.max(value, 128), 8192);
      setTokenSize(clampedValue);
    } else {
      setTokenSize(256);
    }
  };


  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      content: input.trim(),
      isUser: true,
      timestamp: new Date(),
      traceId: "",
      Citation: [],
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);


    try {
      let fileId: number[] = [];
      if (selectedDocs.length === 0) {
        fileId.push(0);
      }
      if (selectedDocs.length > 0) {
        for (const doc of selectedDocs) {
          const docName = doc.label;
          const idRes = await axios.get<{ file_id: number }>(
            `${config?.base_url}/datastores/${
              chatbot.datastoreId
            }/files/${encodeURIComponent(docName)}/id`
          );
          fileId.push(idRes.data.file_id);
        }
      }


      const response: any = await onSendMessage({
        question: input.trim(),
        fileId,
        optimizer: tempSettings.optimizer,
        embeddingModel: tempSettings.embeddingModel,
        llmModel: tempSettings.llmModel,
        vectorDb: tempSettings.vectorDb,
        temperature: tempSettings.temperature,
        guardrailOption: tempSettings.guardrailOption,
        tokenSize: tempSettings.tokenSize,
        showSources: tempSettings.showSources,
        rerankerOption: tempSettings.rerankerOption,
      });


      const botMessage: ChatMessage = {
        id: crypto.randomUUID(),
        content: response["answer"] || response,
        isUser: false,
        timestamp: new Date(),
        traceId: response["traceId"],
        Citation: response["citations"] || [],
      };
      console.log("Bot message with citations:", botMessage.Citation);
      setMessages((prev) => [...prev, botMessage]);
    } catch (error: any) {
      console.error("handleSend error:", error);
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        content:
          error?.message ||
          String(error) ||
          "Failed to send message or fetch file ID.",
        isUser: false,
        timestamp: new Date(),
        traceId: "",
        Citation: [],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };


  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };


  const toggleListening = () => {
    const SpeechRecognition =
      typeof window !== "undefined" &&
      (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!SpeechRecognition) {
      toast({
        title: "Not Supported",
        description: "Speech recognition is not supported in your browser.",
        variant: "destructive",
      });
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    if (isListening) {
      recognition.stop();
      setIsListening(false);
    } else {
      setIsListening(true);
      toast({
        title: "Listening...",
        description: "Speak your question now.",
      });
      recognition.start();
      recognition.onresult = (event: SpeechRecognitionEvent) => {
        const transcript = event.results[0][0].transcript;
        setInput(transcript);
        setIsListening(false);
      };
      recognition.onerror = (event: any) => {
        console.error("Speech recognition error:", event.error);
        toast({
          title: "Error",
          description: `Speech recognition failed: ${event.error}`,
          variant: "destructive",
        });
        setIsListening(false);
      };
      recognition.onend = () => {
        setIsListening(false);
      };
    }
  };


  const toggleSpeech = (message: string) => {
    if ("speechSynthesis" in window) {
      if (isSpeaking) {
        window.speechSynthesis.cancel();
        setIsSpeaking(false);
      } else {
        const utterance = new SpeechSynthesisUtterance(message);
        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => setIsSpeaking(false);
        window.speechSynthesis.speak(utterance);
      }
    } else {
      toast({
        title: "Not Supported",
        description: "Text-to-speech is not supported in your browser.",
        variant: "destructive",
      });
    }
  };


  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };


  const [open, setOpen] = useState(false);
  const [tempSettings, setTempSettings] = useState({
    optimizer: "",
    embeddingModel: "",
    llmModel: "",
    vectorDb: "",
    guardrailOption: "",
    temperature: 0.7,
    tokenSize: 512,
    showSources: true,
    rerankerOption: "none",
  });


  useEffect(() => {
    if (!chatbot?.id) return;
    const saved = localStorage.getItem(`model-settings-${chatbot.id}`);
    if (saved) {
      setTempSettings(JSON.parse(saved));
    }
  }, [chatbot?.id]);


  const handleSave = (overrides: Partial<typeof tempSettings> = {}) => {
    const settings = { ...tempSettings, ...overrides };
    try {
      localStorage.setItem(
        `model-settings-${chatbot.id}`,
        JSON.stringify(settings)
      );
      setTempSettings(settings);
      setOpen(false);
    } catch (err) {
      console.error("Error saving settings:", err);
    }
  };


  const handleCancel = () => {
    const saved = localStorage.getItem(`model-settings-${chatbot.id}`);
    if (saved) {
      setTempSettings(JSON.parse(saved));
    }
    setOpen(false);
  };


  const customMultiStyles = {
    control: (base: any) => ({
      ...base,
      minHeight: 40,
      borderRadius: 8,
      fontSize: 14,
      paddingLeft: 2,
      borderColor: "#d1d5db",
      boxShadow: "none",
      "&:hover": { borderColor: "#9ca3af" },
    }),
    menu: (base: any) => ({ ...base, zIndex: 50, fontSize: 14 }),
    option: (base: any, { isFocused }: any) => ({
      ...base,
      backgroundColor: isFocused ? "#f3f4f6" : "white",
      color: "#111827",
      cursor: "pointer",
    }),
    multiValue: (base: any) => ({
      ...base,
      backgroundColor: "#e5e7eb",
      borderRadius: 4,
      padding: "2px 6px",
    }),
    multiValueLabel: (base: any) => ({
      ...base,
      color: "#111827",
      fontWeight: 500,
    }),
    multiValueRemove: (base: any) => ({
      ...base,
      color: "#6b7280",
      ":hover": { backgroundColor: "#d1d5db", color: "#111827" },
    }),
  };


  const languages = config?.languages || [];


  const onFeedback = async (messageId: string, feedback: string) => {
    if (!config?.base_url) return;
    const message = messages.find((m) => m.id === messageId);
    if (!message || !message.traceId) {
      toast({
        title: "Cannot Submit Feedback",
        description: "A unique trace ID was not found for this message.",
        variant: "destructive",
      });
      return;
    }
    try {
      await axios.post(`${config.base_url}/feedback`, {
        trace_id: message.traceId,
        feedback: feedback,
      });
      toast({
        title: "Success",
        description: "Thank you for your feedback!",
      });
    } catch (error) {
      console.error("Failed to send feedback:", error);
      toast({
        title: "Feedback Error",
        description: "There was a problem submitting your feedback.",
        variant: "destructive",
      });
    }
  };


  const [comment, setComment] = React.useState("");
  const handleCommentSubmit = (messageId: string) => {
    if (!comment.trim()) {
      return;
    }
    onFeedback(messageId, comment);
    setComment("");
    setOpenPopoverId(null);
  };


  return (
    <div className="flex flex-col h-[470px] bg-gradient-surface rounded-lg border border-chatbot-primary/20">
      <ScrollArea ref={scrollAreaRef} className="flex-1 p-4">
        <div className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${
                message.isUser ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[80%] ${
                  message.isUser ? "order-2" : "order-1"
                }`}
              >
                <Card
                  className={`${
                    message.isUser
                      ? "bg-chatbot-primary text-primary-foreground"
                      : "bg-chatbot-secondary border-chatbot-primary/20"
                  }`}
                >
                  <CardContent className="p-3">
                    <p className="text-sm whitespace-pre-wrap">
                      {message.content}
                    </p>


                    {!message.isUser && (
                      <div className="mt-3 flex flex-col gap-2">
                        {/* SOURCES BOX */}


                        {Array.isArray(message.Citation) &&
                        message.Citation.length > 0 ? (
                          <div className="w-full rounded-lg border border-border/40 bg-muted/10 p-2">
                            <span className="font-medium text-sm text-gray-700 mb-1 block">
                              Sources:
                            </span>
                            <div className="flex flex-col gap-1">
                              {message.Citation.map((citation, index) => {
                                const filename = getFilenameFromPath(
                                  citation.source
                                );
                                const pages =
                                  citation.pages && citation.pages.length > 0
                                    ? `(${citation.pages.join(", ")})`
                                    : "";


                                return (
                                  <div
                                    key={citation.source || index}
                                    className="flex items-center text-xs bg-blue-50 rounded-md px-2 py-1"
                                  >
                                    <span className="text-blue-800 mr-1">
                                      [{index + 1}]
                                    </span>
                                    <a
                                      href="#"
                                      onClick={(e) =>
                                        handleFileClick(
                                          e,
                                          chatbot.datastoreId,
                                          filename,
                                          citation.pages?.at(0)
                                        )
                                      }
                                      className="font-medium text-blue-600 hover:underline truncate"
                                    >
                                      {filename}
                                    </a>
                                    {pages && (
                                      <span className="ml-1 text-blue-600 opacity-90 whitespace-nowrap">
                                        {pages}
                                      </span>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ) : (
                          <div className="w-full rounded-lg border border-border/40 bg-muted/10 p-2 text-sm text-muted-foreground">
                            No sources provided.
                          </div>
                        )}


                        {/* FOOTER ACTIONS */}
                        <div className="flex items-center justify-between mt-1">
                          <span className="text-xs opacity-70">
                            {formatTime(message.timestamp)}
                          </span>


                          <div className="flex items-center gap-2">
                            {/*
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-6 w-6 rounded-full text-[11px] border border-border/40 text-muted-foreground hover:bg-muted/70 transition-colors"
                              onClick={() => toggleSpeech(message.content)}
                            >
                              {isSpeaking ? (
                                <VolumeX size={14} />
                              ) : (
                                <Volume2 size={14} />
                              )}
                            </Button>
                           
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-6 w-6 rounded-full text-[11px] border border-border/40 text-green-500 hover:bg-muted/70 transition-colors"
                              onClick={() => onFeedback(message.id, "Positive")}
                            >
                              <ThumbsUp size={14} />
                            </Button>


                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-6 w-6 rounded-full text-[11px] border border-border/40 text-red-500 hover:bg-muted/70 transition-colors"
                              onClick={() => onFeedback(message.id, "Negative")}
                            >
                              <ThumbsDown size={14} />
                            </Button>


                            <Popover
                              open={openPopoverId === message.id}
                              onOpenChange={(isOpen) =>
                                setOpenPopoverId(isOpen ? message.id : null)
                              }
                            >
                              <PopoverTrigger asChild>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-6 w-6 rounded-full text-[11px] border border-border/40 text-blue-500 hover:bg-muted/70 transition-colors"
                                >
                                  <Info size={14} />
                                </Button>
                               
                              </PopoverTrigger>
                              <PopoverContent className="w-64">
                                <div className="space-y-2">
                                  <Label htmlFor={`comment-${message.id}`}>
                                    Comment
                                  </Label>
                                  <Input
                                    id={`comment-${message.id}`}
                                    placeholder="Enter your feedback"
                                    value={comment}
                                    onChange={(e) => setComment(e.target.value)}
                                  />
                                  <Button
                                    size="sm"
                                    className="w-full"
                                    onClick={() =>
                                      handleCommentSubmit(message.id)
                                    }
                                  >
                                    Submit
                                  </Button>
                                 
                                </div>
                              </PopoverContent>
                            </Popover>
                              */}
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-6 w-6 rounded-full text-[11px] border border-border/40 text-muted-foreground hover:bg-muted/70 transition-colors"
                                >
                                  🌐
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent
                                align="end"
                                side="top"
                                className="w-32 max-h-60 overflow-y-auto rounded-lg shadow-md border border-border/40 bg-background p-1 text-sm"
                              >
                                {languages.map((lang) => (
                                  <DropdownMenuItem
                                    key={lang.code}
                                    onClick={() =>
                                      handleTranslate(
                                        message.id,
                                        message.content,
                                        lang.code
                                      )
                                    }
                                    className="cursor-pointer hover:bg-muted rounded-md px-2 py-1"
                                  >
                                    {lang.name}
                                  </DropdownMenuItem>
                                ))}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <Card className="bg-chatbot-secondary border-chatbot-primary/20">
                <CardContent className="p-3">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-chatbot-primary rounded-full animate-bounce" />
                      <div
                        className="w-2 h-2 bg-chatbot-primary rounded-full animate-bounce"
                        style={{ animationDelay: "0.1s" }}
                      />
                      <div
                        className="w-2 h-2 bg-chatbot-primary rounded-full animate-bounce"
                        style={{ animationDelay: "0.2s" }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">
                      Thinking...
                    </span>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </ScrollArea>
      <div>
        <div className="flex gap-4 ml-4 mb-2 ">
          <Button
            variant={isListening ? "destructive" : "chatbot-secondary"}
            size="icon"
            onClick={toggleListening}
            disabled={isLoading}
          >
            {isListening ? (
              <MicOff className="h-4 w-4" />
            ) : (
              <Mic className="h-4 w-4" />
            )}
          </Button>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me anything..."
            disabled={isLoading}
            className="flex-1 border border-chatbot-primary/40"
          />
          <Button
            variant="chatbot"
            className="flex gap-4 mr-4"
            size="icon"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <div className="max-h-[150px] overflow-y-auto px-4 py-2 border-t border-chatbot-primary/20 space-y-2">
          <div className="flex items-center flex-wrap gap-5 px-4 py-2 border-t border-chatbot-primary/20">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="default">
                  Documents
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[300px] h-[200px] max-h-[400px] overflow-y-auto">
                <div className="space-y-2">
                  <Label>Select Documents</Label>
                  <SelectMulti
                    isMulti={true}
                    styles={customMultiStyles}
                    options={getChatbotDocumentOptions(chatbot)}
                    value={selectedDocs}
                    onChange={(selected: any) =>
                      setSelectedDocs(selected || [])
                    }
                    isDisabled={isLoading}
                    placeholder="Choose document"
                  />
                  <div className="space-y-2">
                    <Label>Enter Website URL</Label>
                    <div className="flex gap-2">
                      <Input
                        type="url"
                        placeholder="https://example.com"
                        value={urlInput}
                        onChange={(e) => setUrlInput(e.target.value)}
                        disabled={isLoading}
                      />
                      <Button
                        variant="chatbot"
                        size="sm"
                        onClick={handleUrlSubmit}
                        disabled={!urlInput.trim() || isSubmitting}
                      >
                        {isSubmitting ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          "Add"
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              </PopoverContent>
            </Popover>
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="default">
                  Model Settings
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-4xl h-[90vh] flex flex-col rounded-2xl p-0 overflow-hidden border-2">
                <DialogHeader className="px-6 py-4 border-b bg-muted/40">
                  <DialogTitle className="text-xl font-semibold">
                    Model Settings
                  </DialogTitle>
                  <DialogDescription>
                    Configure optimizer, embeddings, LLM, safety filters, and
                    output preferences.
                  </DialogDescription>
                </DialogHeader>
                <div className="flex-1 overflow-y-auto px-6 py-4 space-y-8">
                  <div>
                    <h3 className="text-lg font-medium mb-2">
                      Response Control
                    </h3>
                    <Separator className="mb-4" />
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-1">
                        <Label>LLM Model</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({
                              ...tempSettings,
                              llmModel: value,
                            })
                          }
                          disabled={isLoading}
                        >
                          <SelectTrigger className="border-2 border-gray-500" >
                            <SelectValue
                              placeholder={
                                tempSettings.llmModel !== ""
                                  ? tempSettings.llmModel
                                  : "Select LLM"
                              }
                            />
                          </SelectTrigger >
                          <SelectContent>
                            {config?.llm_models.map((model) => (
                              <SelectItem key={model} value={model}>
                                {model}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label>Token Size</Label>
                        <Input
                          type="number"
                          className="border-4 border-gray-200"
                          min={config?.token_size_options?.min ?? 256}
                          max={config?.token_size_options?.max ?? 2048}
                          step={config?.token_size_options?.step ?? 128}
                          placeholder={`Default: ${
                            config?.token_size_options?.default ?? 512
                          }`}
                          value={tempSettings.tokenSize}
                          onChange={(e) =>
                            setTempSettings({
                              ...tempSettings,
                              tokenSize: Number(e.target.value),
                            })
                          }
                          disabled={isLoading}
                        />
                        <p className="text-xs text-muted-foreground">
                          Must be between 256 and 2048 tokens (step 128).
                        </p>
                      </div>
                      <div className="space-y-1">
                        <Label>Guardrails</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({
                              ...tempSettings,
                              guardrailOption: value,
                            })
                          }
                          disabled={isLoading}
                        >
                          <SelectTrigger className="border-4 border-gray-200">
                            <SelectValue
                              placeholder={
                                tempSettings.guardrailOption !== ""
                                  ? tempSettings.guardrailOption
                                  : "Select Guardrail Level"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            {config?.guardrail_options.map((option) => (
                              <SelectItem
                                key={option.value}
                                value={option.value}
                              >
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Creativity</Label>
                        <Slider
                          min={0}
                          max={1}
                          step={0.1}
                          value={[tempSettings.temperature]}
                          onValueChange={(val) =>
                            setTempSettings({
                              ...tempSettings,
                              temperature: val[0],
                            })
                          }
                          disabled={isLoading}
                        />
                        <p className="text-sm text-muted-foreground">
                          Temperature: {tempSettings.temperature.toFixed(1)}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div>
                    <h3 className="text-lg font-medium mb-2">
                      Advanced Settings
                    </h3>
                    <Separator className="mb-4" />
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-1">
                        <Label>Query Optimizer</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({
                              ...tempSettings,
                              optimizer: value,
                            })
                          }
                          disabled={isLoading}
                        >
                          <SelectTrigger className="border-4 border-gray-200">
                            <SelectValue
                              placeholder={
                                tempSettings.optimizer !== ""
                                  ? tempSettings.optimizer
                                  : "Select Optimizer"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            {config?.optimizer.map((opt) => (
                              <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label>Embedding Model</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({
                              ...tempSettings,
                              embeddingModel: value,
                            })
                          }
                          disabled
                        >
                          <SelectTrigger className="border-4 border-gray-200">
                            <SelectValue
                              placeholder={
                                tempSettings.embeddingModel !== ""
                                  ? tempSettings.embeddingModel
                                  : "all-MiniLM-L6-v2"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all-MiniLM-L6-v2">
                              all-MiniLM-L6-v2
                            </SelectItem>
                            <SelectItem value="sentence-transformers/all-mpnet-base-v2">
                              sentence-transformers
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label>Vector DB</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({
                              ...tempSettings,
                              vectorDb: value,
                            })
                          }
                          disabled
                        >
                          <SelectTrigger className="border-4 border-gray-200">
                            <SelectValue
                              placeholder={
                                tempSettings.vectorDb !== ""
                                  ? tempSettings.vectorDb
                                  : "FAISS"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="faiss">FAISS</SelectItem>
                            <SelectItem value="chroma">CHROMA</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label>Re-ranker</Label>
                        <select
                          className="w-full rounded-lg border-4 border-gray-200 border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"                          value={tempSettings.rerankerOption}
                          onChange={(e) =>
                            setTempSettings({
                              ...tempSettings,
                              rerankerOption: e.target.value,
                            })
                          }
                          disabled={isLoading}
                        >
                          <option value="none">
                            None – Use retriever results directly
                          </option>
                          <option value="cross-encoder">
                            Cross-encoder – Most accurate, but slower
                          </option>
                          <option value="bi-encoder">
                            Bi-encoder – Faster, less accurate
                          </option>
                          <option value="llm-reranker">
                            LLM-based – Uses a language model
                          </option>
                        </select>
                        <p className="text-xs text-muted-foreground">
                          Choose a re-ranking method to reorder retrieved
                          documents.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
                <DialogFooter className="px-6 py-4 border-t bg-muted/40 flex justify-end gap-3">
                  <Button variant="outline" onClick={handleCancel}>
                    Cancel
                  </Button>
                  <Button onClick={() => handleSave()}>Save Settings</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
          {selectedDocs.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2 items-center">
              <Label className="text-sm text-muted-foreground">Selected:</Label>
              {selectedDocs.map((doc) => (
                <span
                  key={doc.value}
                  className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1"
                >
                  {doc.label}
                  <button
                    type="button"
                    className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                    onClick={() => handleRemove(doc.value)}
                  >
                    <X size={10} strokeWidth={2} />
                  </button>
                </span>
              ))}
            </div>
          )}
          {(tempSettings.optimizer ||
            tempSettings.embeddingModel ||
            tempSettings.llmModel ||
            tempSettings.vectorDb ||
            typeof tempSettings.temperature === "number" ||
            tempSettings.guardrailOption ||
            tempSettings.tokenSize ||
            tempSettings.rerankerOption !== "none" ||
            typeof tempSettings.showSources === "boolean") && (
            <div className="flex flex-wrap gap-2 mt-2 items-center">
              <Label className="text-sm text-muted-foreground">Settings:</Label>
              {tempSettings.optimizer && (
                <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                  Optimizer: {tempSettings.optimizer}
                  <button
                    type="button"
                    className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                    onClick={() => handleSave({ optimizer: "" })}
                  >
                    <X size={10} strokeWidth={2} />
                  </button>
                </span>
              )}
              {tempSettings.embeddingModel && (
                <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                  Embedding: {tempSettings.embeddingModel}
                  <button
                    type="button"
                    className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                    onClick={() => handleSave({ embeddingModel: "" })}
                  >
                    <X size={10} strokeWidth={2} />
                  </button>
                </span>
              )}
              {tempSettings.llmModel && (
                <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                  LLM: {tempSettings.llmModel}
                  <button
                    type="button"
                    className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                    onClick={() => handleSave({ llmModel: "" })}
                  >
                    <X size={10} strokeWidth={2} />
                  </button>
                </span>
              )}
              {tempSettings.vectorDb && (
                <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                  Vector DB: {tempSettings.vectorDb}
                  <button
                    type="button"
                    className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                    onClick={() => handleSave({ vectorDb: "" })}
                  >
                    <X size={10} strokeWidth={2} />
                  </button>
                </span>
              )}
              {typeof tempSettings.temperature === "number" && (
                <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                  Temperature: {tempSettings.temperature}
                  <button
                    type="button"
                    className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                    onClick={() => handleSave({ temperature: 0.0 })}
                  >
                    <X size={10} strokeWidth={2} />
                  </button>
                </span>
              )}
              {tempSettings.guardrailOption && (
                <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                  Guardrails: {tempSettings.guardrailOption}
                  <button
                    type="button"
                    className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                    onClick={() => handleSave({ guardrailOption: "" })}
                  >
                    <X size={10} strokeWidth={2} />
                  </button>
                </span>
              )}
              {tempSettings.tokenSize && (
                <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                  Token Size: {tempSettings.tokenSize}
                  <button
                    type="button"
                    className="flex items-center justify-center  w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                    onClick={() => handleSave({ tokenSize: 256 })}
                  >
                    <X size={10} strokeWidth={2} />
                  </button>
                </span>
              )}
              {tempSettings.rerankerOption !== "none" && (
                <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                  Re-ranker: {tempSettings.rerankerOption}
                  <button
                    type="button"
                    className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                    onClick={() => handleSave({ rerankerOption: "none" })}
                  >
                    <X size={10} strokeWidth={2} />
                  </button>
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};





