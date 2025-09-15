import { useState, useRef, useEffect } from 'react';
import { Send, Mic, MicOff, Volume2, VolumeX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Chatbot, ChatMessage } from '@/types/chatbot';
import { useToast } from '@/hooks/use-toast';
import { Label } from "@/components/ui/label";
// import { Chatbot, CreateChatbotData, QnAPair, RawDatastore,FileRecord } from '@/types/chatbot';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Slider } from "@/components/ui/slider";
import { Info } from "lucide-react"; // icon for tooltips
import { X } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Loader2 } from "lucide-react";

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
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useConfigOptions } from "@/hooks/useConfigOptions"



interface QueryPayload {
  question: string;
  fileId: number[];
  optimizer: string;
  embeddingModel: string;
  llmModel: string;
  vectorDb: string;
  temperature: number;
  guardrailOption: string;
  tokenSize: number; // New field for token size,  
  showSources: boolean; // New field to control source display:
  rerankerOption: string; // New field for reranker option

}

interface ChatInterfaceProps {
  chatbot: Chatbot;
  chatbotName: string;
  // onSendMessage: (message: string) => Promise<string>;
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

export const ChatInterface = ({ chatbot, chatbotName, onSendMessage }: ChatInterfaceProps) => {

  const { config, loading } = useConfigOptions()

  const storageKey = `chat_history_${chatbot?.id}`;
  // Add this type near your ChatMessage interface
  type StoredChatMessage = Omit<ChatMessage, "timestamp"> & { timestamp: string };

  // Update your state initialization
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      try {
        const parsed: StoredChatMessage[] = JSON.parse(saved);

        // Convert timestamp string back to Date
        return parsed.map((msg) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        }));
      } catch (err) {
        console.error("Failed to parse saved messages:", err);
        return [];
      }
    }

    // Default greeting
    return [
      {
        id: "1",
        content: `Hello, I am your ${chatbot.name}. How can I help you today?`,
        isUser: false,
        timestamp: new Date(),
      },
    ];
  });


  useEffect(() => {
    const toStore: StoredChatMessage[] = messages.map((msg) => ({
      ...msg,
      timestamp: msg.timestamp.toISOString(), // Convert Date → string
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
              originalContent: msg.originalContent || msg.content, // ✅ preserve original
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




  const [input, setInput] = useState('');
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

  const getChatbotDocumentOptions = (chatbot: { documents?: string[] }): DocumentOption[] => {
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
        {}, // empty body
        { params: { url } } // URL as query param
      );
      return data; // { url, file_path, message }
    } catch (err: any) {
      console.error("Error scraping website:", err.response?.data || err.message);
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

      // ✅ Show toast instead of auto-refresh
      toast({
        title: "Website processed successfully 🎉",
        description:
          "Please refresh the page and select the scraped URL file from the 'Select Documents' option.",
        duration: 10000, // auto-dismiss after 5s
      });

      // Optional: update parent state if needed
      setUrlInput(""); // reset input
      return result;
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Optional helper to make labels more readable
  const getFormattedLabel = (filename: string): string => {
    // Remove extension and convert snake_case or kebab-case to title case
    const nameWithoutExt = filename.replace(/\.[^/.]+$/, "");
    return nameWithoutExt
      .replace(/[_\-]/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase()); // Capitalize each word
  };

  // Component part (inside your main component)
  const [selectedDocs, setSelectedDocs] = useState<DocumentOption[]>([]);
  const [documentOptions, setDocumentOptions] = useState<DocumentOption[]>([]);

  const handleRemove = (value: string) => {
    setSelectedDocs((prevDocs) => prevDocs.filter((doc) => doc.value !== value));
  };

  // Automatically update options when chatbot documents change
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
    // Auto-scroll to bottom when new messages are added
    if (scrollAreaRef.current) {
      const scrollContainer = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (scrollContainer) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
      }
    }
  }, [messages]);

  const handleTokenSizeChange = (e) => {
    const value = parseInt(e.target.value, 10);

    if (!isNaN(value)) {
      // clamp value between 128 and 8192
      const clampedValue = Math.min(Math.max(value, 128), 8192);
      setTokenSize(clampedValue);
    } else {
      setTokenSize(256); // reset if invalid
    }
  };
  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      content: input.trim(),
      isUser: true,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      let fileId = [];
      if (selectedDocs.length == 0) {
        fileId.push(0);
      }

      if (selectedDocs.length > 0) {

        for (const doc of selectedDocs) {
          const docName = doc.label;
          const idRes = await axios.get<{ file_id: number }>(
            `${config?.base_url}/datastores/${chatbot.datastoreId}/files/${encodeURIComponent(docName)}/id`
          );
          fileId.push(idRes.data.file_id);
        }
      }



      // ✅ Step 2: Call main retriever API using file ID and other query params
      const response = await onSendMessage({
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
        content: response,
        isUser: false,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error("handleSend error:", error);

      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        content: error?.message || String(error) || "Failed to send message or fetch file ID.",
        isUser: false,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };




  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
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
        setInput(transcript); // 👈 Store final transcript into inputText or your message state
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
    if ('speechSynthesis' in window) {
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
    return new Intl.DateTimeFormat('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  const [open, setOpen] = useState(false);
  // const [optimizer, setOptimizer] = useState("");
  // const [embeddingModel, setEmbeddingModel] = useState("");
  // const [llmModel, setLlmModel] = useState("");
  // const [vectorDb, setVectorDb] = useState("");
  // const [guardrailOption, setGuardrailOption] = useState("");
  // const [temperature, setTemperature] = useState(0);
  // const [rerankerOption, setRerankerOption] = useState<string>("none")
  // const handleRerankerChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
  //   setRerankerOption(e.target.value)
  // }

  // Keep everything in one object
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

  // Load settings from localStorage on mount
  useEffect(() => {
    if (!chatbot?.id) return;

    const saved = localStorage.getItem(`model-settings-${chatbot.id}`);
    if (saved) {
      setTempSettings(JSON.parse(saved));
    }
  }, [chatbot?.id]);

  // Save → commit changes
  const handleSave = (overrides: Partial<typeof tempSettings> = {}) => {
    const settings = { ...tempSettings, ...overrides };

    try {
      localStorage.setItem(
        `model-settings-${chatbot.id}`,
        JSON.stringify(settings)
      );
      setTempSettings(settings); // keep UI in sync
      setOpen(false);
    } catch (err) {
      console.error("Error saving settings:", err);
    }
  };

  // Cancel → restore last saved
  const handleCancel = () => {
    const saved = localStorage.getItem(`model-settings-${chatbot.id}`);
    if (saved) {
      setTempSettings(JSON.parse(saved));
    }
    setOpen(false);
  };





  const customMultiStyles = {
    control: (base) => ({
      ...base,
      minHeight: 40,
      borderRadius: 8,
      fontSize: 14,
      paddingLeft: 2,
      borderColor: '#d1d5db', // Tailwind gray-300
      boxShadow: 'none',
      '&:hover': {
        borderColor: '#9ca3af', // Tailwind gray-400
      },
    }),
    menu: (base) => ({
      ...base,
      zIndex: 50,
      fontSize: 14,
    }),
    option: (base, { isFocused }) => ({
      ...base,
      backgroundColor: isFocused ? '#f3f4f6' : 'white', // Tailwind gray-100
      color: '#111827', // Tailwind gray-900
      cursor: 'pointer',
    }),
    multiValue: (base) => ({
      ...base,
      backgroundColor: '#e5e7eb', // Tailwind gray-200
      borderRadius: 4,
      padding: '2px 6px',
    }),
    multiValueLabel: (base) => ({
      ...base,
      color: '#111827',
      fontWeight: 500,
    }),
    multiValueRemove: (base) => ({
      ...base,
      color: '#6b7280',
      ':hover': {
        backgroundColor: '#d1d5db',
        color: '#111827',
      },
    }),
  };
  const languages = config?.languages || [];


  return (
    <div className="flex flex-col h-[470px] bg-gradient-surface rounded-lg border border-chatbot-primary/20">

      {/* Chat Messages */}
      <ScrollArea ref={scrollAreaRef} className="flex-1 p-4">
        <div className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.isUser ? "justify-end" : "justify-start"}`}
            >
              <div className={`max-w-[80%] ${message.isUser ? "order-2" : "order-1"}`}>
                <Card
                  className={`${message.isUser
                    ? "bg-chatbot-primary text-primary-foreground"
                    : "bg-chatbot-secondary border-chatbot-primary/20"
                    }`}
                >
                  <CardContent className="p-3">
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>

                    <div className="flex flex-col gap-2 mt-2">
                      {/* Time + Actions */}
                      <div className="flex items-center justify-between">
                        <span className="text-xs opacity-70">
                          {formatTime(message.timestamp)}
                        </span>


                      </div>
                      {/* Translate Button + Dropdown */}
                      {!message.isUser && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <div className="flex justify-end mt-1">
                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-6 w-6 rounded-full text-[11px] border border-border/40 text-muted-foreground hover:bg-muted/70 transition-colors flex items-center justify-center"
                              >
                                🌐
                              </Button>
                            </div>

                          </DropdownMenuTrigger>
                          <DropdownMenuContent
                            align="end"
                            side="top"
                            className="w-32 max-h-60 overflow-y-auto rounded-lg shadow-md border border-border/40 bg-background p-1 text-sm"

                          >
                            {languages.map((lang) => (
                              <DropdownMenuItem
                                key={lang.code}
                                onClick={() => handleTranslate(message.id, message.content, lang.code)}
                                className="cursor-pointer hover:bg-muted rounded-md px-2 py-1"
                              >
                                {lang.name}
                              </DropdownMenuItem>
                            ))}
                          </DropdownMenuContent>

                        </DropdownMenu>

                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div >
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <Card className="bg-chatbot-secondary border-chatbot-primary/20">
                <CardContent className="p-3">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-chatbot-primary rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-chatbot-primary rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-chatbot-primary rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                    <span className="text-xs text-muted-foreground">Thinking...</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div >
      </ScrollArea >



      <div>
        {/* Original Input Section */}
        <div className="flex gap-4 ml-4 mb-2 ">
          <Button
            variant={isListening ? "destructive" : "chatbot-secondary"}
            size="icon"
            onClick={toggleListening}
            disabled={isLoading}
          >
            {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
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

            {/* Button 1: Document Selector */}
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
                    value={selectedDocs}  // Only the first selected item
                    onChange={(selected: DocumentOption[] | null) =>
                      setSelectedDocs(selected || [])
                    }
                    isDisabled={isLoading}
                    placeholder="Choose document"
                  />

                  {/* Enter URL */}
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
                        disabled={!urlInput.trim() || isSubmitting} // ✅ disable while submitting
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

            {/* Button 2: Model Settings */}

            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" size="default">Model Settings</Button>
              </DialogTrigger>

              <DialogContent className="max-w-4xl h-[90vh] flex flex-col rounded-2xl p-0 overflow-hidden">
                {/* Header */}
                <DialogHeader className="px-6 py-4 border-b bg-muted/40">
                  <DialogTitle className="text-xl font-semibold">Model Settings</DialogTitle>
                  <DialogDescription>
                    Configure optimizer, embeddings, LLM, safety filters, and output preferences.
                  </DialogDescription>
                </DialogHeader>

                {/* Body */}
                <div className="flex-1 overflow-y-auto px-6 py-4 space-y-8">

                  {/* Query & Models Section */}
                  <div>
                    <h3 className="text-lg font-medium mb-2">Response Control</h3>
                    <Separator className="mb-4" />
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* LLM Model */}
                      <div className="space-y-1">
                        <Label>LLM Model</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({ ...tempSettings, llmModel: value })
                          }
                          disabled={isLoading}
                        >
                          <SelectTrigger>
                            <SelectValue
                              placeholder={
                                tempSettings.llmModel !== "" ? tempSettings.llmModel : "Select LLM"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            {config?.llm_models.map(model => (
                              <SelectItem key={model} value={model}>
                                {model}
                              </SelectItem>
                            ))}
                          </SelectContent>

                        </Select>

                      </div>
                      {/* Token Size */}
                      <div className="space-y-1">
                        <Label>Token Size</Label>
                        <Input
                          type="number"
                          min={config?.token_size_options?.min ?? 256}
                          max={config?.token_size_options?.max ?? 2048}
                          step={config?.token_size_options?.step ?? 128}
                          placeholder={`Default: ${config?.token_size_options?.default ?? 512}`}
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

                      {/* Guardrails */}
                      <div className="space-y-1">
                        <Label>Guardrails</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({ ...tempSettings, guardrailOption: value })
                          }
                          disabled={isLoading}
                        >
                          <SelectTrigger>
                            <SelectValue
                              placeholder={
                                tempSettings.guardrailOption !== ""
                                  ? tempSettings.guardrailOption
                                  : "Select Guardrail Level"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            {config?.guardrail_options.map(option => (
                              <SelectItem key={option.value} value={option.value}>
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>

                        </Select>
                      </div>

                      {/* Temperature */}
                      <div className="space-y-2">
                        <Label>Creativity</Label>
                        <Slider
                          min={0}
                          max={1}
                          step={0.1}
                          value={[tempSettings.temperature]}
                          onValueChange={(val) =>
                            setTempSettings({ ...tempSettings, temperature: val[0] })
                          }
                          disabled={isLoading}
                        />
                        <p className="text-sm text-muted-foreground">
                          Temperature: {tempSettings.temperature.toFixed(1)}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Advanced Section */}
                  <div>
                    <h3 className="text-lg font-medium mb-2">Advanced Settings</h3>
                    <Separator className="mb-4" />
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      {/* Query Optimizer */}
                      <div className="space-y-1">
                        <Label>Query Optimizer</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({ ...tempSettings, optimizer: value })
                          }
                          disabled={isLoading}
                        >
                          <SelectTrigger>
                            <SelectValue
                              placeholder={
                                tempSettings.optimizer !== ""
                                  ? tempSettings.optimizer
                                  : "Select Optimizer"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            {config?.optimizer.map(opt => (
                              <SelectItem key={opt.value} value={opt.value}>
                                {opt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Embedding Model */}
                      <div className="space-y-1">
                        <Label>Embedding Model</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({ ...tempSettings, embeddingModel: value })
                          }
                          disabled
                        >
                          <SelectTrigger>
                            <SelectValue
                              placeholder={
                                tempSettings.embeddingModel !== ""
                                  ? tempSettings.embeddingModel
                                  : "all-MiniLM-L6-v2"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all-MiniLM-L6-v2">all-MiniLM-L6-v2</SelectItem>
                            <SelectItem value="sentence-transformers/all-mpnet-base-v2">
                              sentence-transformers
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Vector DB */}
                      <div className="space-y-1">
                        <Label>Vector DB</Label>
                        <Select
                          onValueChange={(value) =>
                            setTempSettings({ ...tempSettings, vectorDb: value })
                          }
                          disabled
                        >
                          <SelectTrigger>
                            <SelectValue
                              placeholder={
                                tempSettings.vectorDb !== "" ? tempSettings.vectorDb : "FAISS"
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="faiss">FAISS</SelectItem>
                            <SelectItem value="chroma">CHROMA</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Sources Toggle
                      <div className="flex items-center justify-between border rounded-lg p-3">
                        <Label htmlFor="sources-toggle">Include Sources in Output</Label>
                        <Switch
                          id="sources-toggle"
                          checked={tempSettings.showSources}
                          onCheckedChange={(checked) =>
                            setTempSettings({ ...tempSettings, showSources: checked })
                          }
                          disabled={isLoading}
                        />
                      </div> */}

                      {/* Re-ranker Option */}
                      <div className="space-y-1">
                        <Label>Re-ranker</Label>
                        <select
                          className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
                          value={tempSettings.rerankerOption}
                          onChange={(e) =>
                            setTempSettings({ ...tempSettings, rerankerOption: e.target.value })
                          }
                          disabled={isLoading}
                        >
                          <option value="none">None – Use retriever results directly</option>
                          <option value="cross-encoder">
                            Cross-encoder – Most accurate, but slower (fine-grained relevance)
                          </option>
                          <option value="bi-encoder">
                            Bi-encoder – Faster, less accurate (lightweight ranking)
                          </option>
                          <option value="llm-reranker">
                            LLM-based – Uses a language model to judge document relevance
                          </option>
                        </select>
                        <p className="text-xs text-muted-foreground">
                          Choose a re-ranking method to reorder retrieved documents before passing
                          them to the LLM.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Footer */}
                {/* Footer */}
                <DialogFooter className="px-6 py-4 border-t bg-muted/40 flex justify-end gap-3">
                  <Button variant="outline" onClick={handleCancel}>Cancel</Button>
                  <Button onClick={() => handleSave()}>Save Settings</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

          </div>
          {
            selectedDocs.length > 0 && (
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

            )
          }
          {
            (
              tempSettings.optimizer ||
              tempSettings.embeddingModel ||
              tempSettings.llmModel ||
              tempSettings.vectorDb ||
              typeof tempSettings.temperature === "number" ||
              tempSettings.guardrailOption ||
              tempSettings.tokenSize ||
              tempSettings.rerankerOption !== "none" ||
              typeof tempSettings.showSources === "boolean"
            ) && (
              <div className="flex flex-wrap gap-2 mt-2 items-center">
                <Label className="text-sm text-muted-foreground">Settings:</Label>

                {tempSettings.optimizer && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    Optimizer: {tempSettings.optimizer}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => {
                        const updated = { ...tempSettings, optimizer: "" };
                        setTempSettings(updated);
                        handleSave({ optimizer: "" });
                      }}
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
                      onClick={() => {
                        const updated = { ...tempSettings, embeddingModel: "" };
                        setTempSettings(updated);
                        handleSave({ embeddingModel: "" });
                      }}
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
                      onClick={() => {
                        const updated = { ...tempSettings, llmModel: "" };
                        setTempSettings(updated);
                        handleSave({ llmModel: "" });
                      }}
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
                      onClick={() => {
                        const updated = { ...tempSettings, vectorDb: "" };
                        setTempSettings(updated);
                        handleSave({ vectorDb: "" });
                      }}
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
                      onClick={() => {
                        const updated = { ...tempSettings, temperature: 0.0 };
                        setTempSettings(updated);
                        handleSave({ temperature: 0.0 });
                      }}
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
                      onClick={() => {
                        const updated = { ...tempSettings, guardrailOption: "" };
                        setTempSettings(updated);
                        handleSave({ guardrailOption: "" });
                      }}
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
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => {
                        const updated = { ...tempSettings, tokenSize: 256 };
                        setTempSettings(updated);
                        handleSave({ tokenSize: 256 });
                      }}
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
                      onClick={() => {
                        const updated = { ...tempSettings, rerankerOption: "none" };
                        setTempSettings(updated);
                        handleSave({ rerankerOption: "none" });
                      }}
                    >
                      <X size={10} strokeWidth={2} />
                    </button>
                  </span>
                )}


                {/* Include Sources */}
                {/* {typeof showSources === "boolean" && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    Sources: {showSources ? "Yes" : "No"}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => {setShowSources(false);
                        handleSave({ showSources: false });
                      }} // reset to "No"
                    >
                      <X size={10} strokeWidth={2} />
                    </button>
                  </span> */}
                {/* )} */}

              </div>
            )
          }




        </div >

      </div >
    </div >
  );
};