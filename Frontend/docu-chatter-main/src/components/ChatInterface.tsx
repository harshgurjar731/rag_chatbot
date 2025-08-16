import { useState, useRef, useEffect } from 'react';
import { Send, Mic, MicOff, Volume2, VolumeX } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Chatbot, ChatMessage } from '@/types/chatbot';
import { useToast } from '@/hooks/use-toast';
// import { useState } from "react";
// import { Mic, MicOff, Send } from "lucide-react";
// import { Button } from "@/components/ui/button";
// import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
// import { Chatbot, CreateChatbotData, QnAPair, RawDatastore,FileRecord } from '@/types/chatbot';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Slider } from "@/components/ui/slider";
import { Info } from "lucide-react"; // icon for tooltips
import { X } from "lucide-react";
import { Switch } from "@/components/ui/switch";

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

interface QueryPayload {
  question: string;
  fileId: number | null;
  optimizer: string;
  embeddingModel: string;
  llmModel: string;
  vectorDb: string;
  temperature: number;
  guardrailOption: string;
  tokenSize: number; // New field for token size,  
  showSources: boolean; // New field to control source display

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

  const storageKey = `chat_history_${chatbot?.id}`;
  // const [messages, setMessages] = useState<ChatMessage[]>([
  //   {
  //     id: '1',
  //     content: `Hello! I'm ${chatbotName}. How can I assist you today?`,
  //     isUser: false,
  //     timestamp: new Date(),
  //   }
  // ]);
  // Save to localStorage on change

  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) {
      try {
        const parsed: ChatMessage[] = JSON.parse(saved);
        return parsed.map((msg) => ({
          ...msg,
          timestamp: new Date(msg.timestamp), // Convert timestamp back to Date
        }));
      } catch {
        return [];
      }
    }

    return [
      {
        id: "1",
        content: `Hello! I'm ${chatbotName}. How can I assist you today?`,
        isUser: false,
        timestamp: new Date(),
      },
    ];
  });

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(messages));
  }, [messages, storageKey]);





  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();
  const [inputText, setInputText] = useState(""); // This holds the speech-to-text result
  const [tokenSize, setTokenSize] = useState(256);
  const [showSources, setShowSources] = useState(false);
  // const storageKey = `chat_history_${chatbot?.id}`; // Unique key per chatbot


  const getChatbotDocumentOptions = (chatbot: { documents?: string[] }): DocumentOption[] => {
    if (!chatbot?.documents || chatbot.documents.length === 0) return [];

    return chatbot.documents.map((doc) => ({
      label: doc,
      value: doc,
    }));
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

  // const handleSend = async () => {
  //   if (!input.trim() || isLoading) return;

  //   const userMessage: ChatMessage = {
  //     id: crypto.randomUUID(),
  //     content: input.trim(),
  //     isUser: true,
  //     timestamp: new Date(),
  //   };

  //   setMessages(prev => [...prev, userMessage]);
  //   setInput('');
  //   setIsLoading(true);

  //   try {
  //     const response = await onSendMessage(input.trim());

  //     const botMessage: ChatMessage = {
  //       id: crypto.randomUUID(),
  //       content: response,
  //       isUser: false,
  //       timestamp: new Date(),
  //     };

  //     setMessages(prev => [...prev, botMessage]);
  //   } catch (error) {
  //     toast({
  //       title: "Error",
  //       description: "Failed to get response from chatbot.",
  //       variant: "destructive",
  //     });
  //   } finally {
  //     setIsLoading(false);
  //   }
  // };
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
      let fileId = null;
      if (selectedDocs.length == 0) {
        fileId = 0;
      }

      // 🔍 Step 1: Get file ID from backend using filename
      if (selectedDocs.length > 0) {
        const docName = selectedDocs[0].label;
        const idRes = await axios.get<{ file_id: number }>(
          `http://localhost:8000/datastores/${chatbot.datastoreId}/files/${encodeURIComponent(docName)}/id`
        );
        fileId = idRes.data.file_id;
      }



      // ✅ Step 2: Call main retriever API using file ID and other query params
      const response = await onSendMessage({
        question: input.trim(),
        fileId,
        optimizer,
        embeddingModel,
        llmModel,
        vectorDb,
        temperature,
        guardrailOption,
        tokenSize,  
        showSources    
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
      toast({
        title: "Error",
        description: "Failed to send message or fetch file ID.",
        variant: "destructive",
      });
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

  // const toggleListening = () => {
  //   if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
  //     toast({
  //       title: "Not Supported",
  //       description: "Speech recognition is not supported in your browser.",
  //       variant: "destructive",
  //     });
  //     return;
  //   }

  //   if (isListening) {
  //     setIsListening(false);
  //     // Stop speech recognition
  //   } else {
  //     setIsListening(true);
  //     // Start speech recognition
  //     toast({
  //       title: "Listening...",
  //       description: "Speak your question now.",
  //     });

  //     // Simulate speech recognition (in a real app, you'd implement actual speech recognition)
  //     setTimeout(() => {
  //       setIsListening(false);
  //       toast({
  //         title: "Speech Recognition",
  //         description: "This is a demo. In a real implementation, your speech would be converted to text.",
  //       });
  //     }, 3000);
  //   }
  // };

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
        setInputText(transcript); // 👈 Store final transcript into inputText or your message state
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

  // const [selectedDocs, setSelectedDocs] = useState<any[]>([]);
  const [optimizer, setOptimizer] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [llmModel, setLlmModel] = useState("");
  const [vectorDb, setVectorDb] = useState("");
  const [guardrailOption, setGuardrailOption] = useState("");
  const [temperature, setTemperature] = useState(0);



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

  return (
    <div className="flex flex-col h-[470px] bg-gradient-surface rounded-lg border border-chatbot-primary/20">

      {/* Chat Messages */}
      <ScrollArea ref={scrollAreaRef} className="flex-1 p-4">
        <div className="space-y-4">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[80%] ${message.isUser ? 'order-2' : 'order-1'}`}>
                <Card className={`${message.isUser
                  ? 'bg-chatbot-primary text-primary-foreground'
                  : 'bg-chatbot-secondary border-chatbot-primary/20'
                  }`}>
                  <CardContent className="p-3">
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs opacity-70">
                        {formatTime(message.timestamp)}
                      </span>
                      {!message.isUser && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => toggleSpeech(message.content)}
                          className="h-6 w-6 p-0 opacity-70 hover:opacity-100"
                        >
                          {isSpeaking ?
                            <VolumeX className="h-3 w-3" /> :
                            <Volume2 className="h-3 w-3" />
                          }
                        </Button>
                      )}
                    </div>
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
                      <div className="w-2 h-2 bg-chatbot-primary rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-chatbot-primary rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                    <span className="text-xs text-muted-foreground">Thinking...</span>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Input Area */}
      {/* <div className="p-4 border-t border-chatbot-primary/20">
        <div className="flex gap-2">
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
            className="flex-1"
          />
          
          <Button
            variant="chatbot"
            size="icon"
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div> */}



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
          {/* <Input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Ask something..."
            className="w-full"
          /> */}

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
                  {/* <SelectMulti
                    isMulti={false}
                    styles={customMultiStyles}
                    options={[getChatbotDocumentOptions(chatbot)] 
                      // ||[]
                    }
                    value={selectedDocs[0] || null} // Expect a single selected object
                    onChange={(selected: { label: string; value: string } | null) =>
                      setSelectedDocs(selected ? [selected] : [])
                    }
                    isDisabled={isLoading}
                    placeholder="Choose document(s)"
                  /> */}
                  <SelectMulti
                    isMulti={false}
                    styles={customMultiStyles}
                    options={getChatbotDocumentOptions(chatbot)}
                    value={selectedDocs[0] || null}  // Only the first selected item
                    onChange={(selected: DocumentOption | null) =>
                      setSelectedDocs(selected ? [selected] : [])
                    }
                    isDisabled={isLoading}
                    placeholder="Choose document"
                  />




                </div>
              </PopoverContent>
            </Popover>

            {/* Button 2: Model Settings */}
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="default">
                  Model Settings
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-72 space-y-2 max-h-80 overflow-y-auto">
                {/* Query Optimizer */}
                <div className="space-y-1">
                  <Label>Query Optimizer</Label>
                  <Select onValueChange={setOptimizer} disabled={isLoading}>
                    <SelectTrigger>
                      <SelectValue placeholder={optimizer != "" ? optimizer : "Select Optimizer"} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None</SelectItem>
                      <SelectItem value="Multi Query">Multi Query</SelectItem>
                      {/* <SelectItem value="hybrid">Hybrid</SelectItem> */}
                    </SelectContent>
                  </Select>
                </div>

                {/* Embedding Model */}
                <div className="space-y-1">
                  <Label>Embedding Model</Label>
                  <Select onValueChange={setEmbeddingModel} disabled={isLoading}>
                    <SelectTrigger>
                      <SelectValue placeholder={embeddingModel != "" ? embeddingModel : "Select Embedding Model"} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all-MiniLM-L6-v2">all-MiniLM-L6-v2</SelectItem>
                      <SelectItem value="sentence-transformers/all-mpnet-base-v2">sentence-transformers</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* LLM Model */}
                <div className="space-y-1">
                  <Label>LLM Model</Label>
                  <Select onValueChange={setLlmModel} disabled={isLoading}>
                    <SelectTrigger>
                      <SelectValue placeholder={llmModel != "" ? llmModel : "Select LLM"} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gemma-7b-it">gemma-7b-it</SelectItem>
                      <SelectItem value="llama3-70b-8192">llama3-70b-8192</SelectItem>
                      <SelectItem value="llama3-8b-8192">llama3-8b-8192</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Vector DB */}
                <div className="space-y-1">
                  <Label>Vector DB</Label>
                  <Select onValueChange={setVectorDb} disabled={isLoading}>
                    <SelectTrigger>
                      <SelectValue placeholder={vectorDb != "" ? vectorDb : "Select Vector DB"} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="faiss">FAISS</SelectItem>
                      <SelectItem value="chroma">CHROMA</SelectItem>
                      {/* <SelectItem value="pinecone">Pinecone</SelectItem> */}
                    </SelectContent>
                  </Select>
                </div>
                {/* Guardrails Selection */}
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <Label>Guardrails</Label>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger>
                          <Info className="h-4 w-4 text-muted-foreground cursor-pointer" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Controls content safety filtering. "Strict" blocks more sensitive or unsafe responses.</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <Select onValueChange={setGuardrailOption} disabled={isLoading}>
                    <SelectTrigger>
                      <SelectValue placeholder={guardrailOption !== "" ? guardrailOption : "Select Guardrail Level"} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None - No filtering</SelectItem>
                      <SelectItem value="basic">Basic - Mild safety filtering</SelectItem>
                      <SelectItem value="strict">Strict - High safety filtering</SelectItem>
                      <SelectItem value="custom">Custom - Use project-defined rules</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Temperature Control */}
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <Label>Creativity</Label>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger>
                          <Info className="h-4 w-4 text-muted-foreground cursor-pointer" />
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Lower = more precise & factual. Higher = more creative & varied responses.</p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                  <Slider
                    min={0}
                    max={1}
                    step={0.1}
                    value={[temperature]}
                    onValueChange={(val) => setTemperature(val[0])}
                    disabled={isLoading}
                  />
                  <p className="text-sm text-muted-foreground">Temperature: {temperature.toFixed(1)}</p>
                </div>
                {/* Token Size */}
                <div className="space-y-1">
                  <Label>Token Size</Label>
                  <Input
                    type="number"
                    min={256}
                    max={2048}
                    step={128}
                    placeholder="Enter token size"
                    value={tokenSize}
                    onChange={handleTokenSizeChange}
                    disabled={isLoading}
                  />
                  <p className="text-xs text-muted-foreground">
                    Must be between 256 and 2048 tokens (step 128).
                  </p>
                </div>
                <div className="flex items-center justify-between space-x-2">
                  <Label htmlFor="sources-toggle">Include Sources in Output</Label>
                  <Switch
                    id="sources-toggle"
                    checked={showSources}
                    onCheckedChange={setShowSources}
                    disabled={isLoading}
                  />
                </div>


              </PopoverContent>
            </Popover>
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
          {(optimizer || embeddingModel || llmModel || vectorDb || typeof temperature === "number" || guardrailOption ||
            tokenSize ||                     // ✅ Token size
            typeof showSources === "boolean") && (
              <div className="flex flex-wrap gap-2 mt-2 items-center">
                <Label className="text-sm text-muted-foreground">Settings:</Label>

                {optimizer && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    Optimizer: {optimizer}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => setOptimizer("")}
                    >
                      <X size={10} strokeWidth={2} />
                    </button>
                  </span>
                )}

                {embeddingModel && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    Embedding: {embeddingModel}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => setEmbeddingModel("")}
                    >
                      <X size={10} strokeWidth={2} />
                    </button>
                  </span>
                )}

                {llmModel && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    LLM: {llmModel}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => setLlmModel("")}
                    >
                      <X size={10} strokeWidth={2} />
                    </button>
                  </span>
                )}

                {vectorDb && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    Vector DB: {vectorDb}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => setVectorDb("")}
                    >
                      <X size={10} strokeWidth={2} />
                    </button>
                  </span>
                )}

                {typeof temperature === "number" && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    Temperature: {temperature}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => setTemperature(0.0)}
                    >
                      <X size={10} strokeWidth={2} />
                    </button>
                  </span>
                )}

                {guardrailOption && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    Guardrails: {guardrailOption}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => setGuardrailOption("")}
                    >
                      <X size={10} strokeWidth={2} />
                    </button>
                  </span>
                )}

                {/* Token Size */}
                {tokenSize && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    Token Size: {tokenSize}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => setTokenSize(256)}
                    >
                      <X size={10} strokeWidth={2} />
                    </button>
                  </span>
                )}

                {/* Include Sources */}
                {typeof showSources === "boolean" && (
                  <span className="flex items-center gap-1 text-xs bg-chatbot-secondary text-foreground border border-chatbot-primary/20 rounded-md px-2 py-1">
                    Sources: {showSources ? "Yes" : "No"}
                    <button
                      type="button"
                      className="flex items-center justify-center w-4 h-4 rounded-full hover:bg-destructive hover:text-destructive-foreground transition-colors duration-150"
                      onClick={() => setShowSources(false)} // reset to "No"
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