import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Trash2, Upload, Plus, FileText, MessageSquarePlus, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { ChatInterface } from '@/components/ChatInterface';
import { useChatbots } from '@/hooks/useChatbots';
import { useToast } from '@/hooks/use-toast';
import { Trash } from "lucide-react"; // Make sure Trash icon is imported
import axios from 'axios';
import qs from "qs";


type FileRecord = {
  id: number;
  filename: string;
  datastore_id: number;
  content_type?: string;
  // add other fields if needed
};


const ChatbotDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { getChatbot, deleteChatbot, addDocument, addQnA } = useChatbots();
  const { toast } = useToast();

  const [newQuestion, setNewQuestion] = useState('');
  const [newAnswer, setNewAnswer] = useState('');
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [newFile, setNewFile] = useState<File | null>(null);
  const { chatbots, setChatbots } = useChatbots();
  const { refetchChatbots } = useChatbots();
  const [isDragging, setIsDragging] = useState(false);
  const chatbot = id ? getChatbot(id) : null;

  if (!chatbot) {
    return (
      <div className="min-h-screen bg-gradient-surface flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-foreground mb-4">Chatbot Not Found</h1>
          <Button onClick={() => navigate('/')} variant="chatbot">
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Button>
        </div>
      </div>
    );
  }
  const handleDeleteDocument = async (chatbotId: string, datastoreId: number, docName: string) => {
    try {
      // 1. Delete the document from backend
      // Step 1: Get file ID using the filename
      const idResponse = await axios.get<{ file_id: number }>(
        `http://127.0.0.1:8000/datastores/${datastoreId}/files/${encodeURIComponent(docName)}/id`
      );

      const fileId = idResponse.data.file_id;

      // Step 2: Delete the file using the file ID
      await axios.delete(
        `http://127.0.0.1:8000/datastores/${datastoreId}/files/${fileId}`
      );

      toast({
        title: "Document Deleted",
        description: `"${docName}" has been removed.`,
      });

      // 2. Refetch the file list for this chatbot's datastore
      const updatedFilesRes = await axios.get<FileRecord[]>(
        `http://127.0.0.1:8000/datastores/${datastoreId}/files`
      );

      const updatedDocuments = updatedFilesRes.data.map((file) => file.filename);
      await refetchChatbots();

      //   // 3. Update chatbot state locally
      // setChatbots((prevChatbots) =>
      //   prevChatbots.map((bot) =>
      //     bot.id === chatbotId
      //       ? {
      //           ...bot,
      //           documents: bot.documents.filter((doc) => doc !== docName),
      //         }
      //       : bot
      //   )
      // );
    } catch (error: any) {
      console.error("Error deleting document:", error);
      toast({
        title: "Error Deleting Document",
        description:
          error.response?.data?.detail || "An error occurred while deleting the document.",
        variant: "destructive",
      });
    }
  };




  // const handleDelete = async () => {
  //   try {
  //     console.log(chatbot.datastoreId)
  //     deleteChatbot(chatbot.id);
  //     await axios.delete(`http://127.0.0.1:8000/datastore/${chatbot.datastoreId}`);
  //     toast({
  //       title: "Chatbot Deleted",
  //       description: `${chatbot.name} has been removed.`,
  //     });
  //     navigate('/');
  //   } catch (error: any) {
  //     toast({
  //       title: "Error Deleting Chatbot and Datastore",
  //       description: error.response?.data?.detail || "An error occurred while deleting.",
  //       variant: "destructive",
  //     });
  //   }
  //   // const handleDelete = () => {

  //   //   toast({
  //   //     title: "Chatbot Deleted",
  //   //     description: `${chatbot.name} has been removed.`,
  //   //   });
  //   //   navigate('/');
  //   // };



  // };
  const handleDelete = async () => {
    try {
      console.log("Deleting chatbot and associated datastore...");
      console.log("Datastore ID:", chatbot.datastoreId);

      // Step 1: Get all files in the datastore
      const filesRes = await axios.get<FileRecord[]>(
        `http://127.0.0.1:8000/datastores/${chatbot.datastoreId}/files`
      );
      const files = filesRes.data;

      // Step 2: Loop through each file and delete it using file ID
      for (const file of files) {
        await axios.delete(
          `http://127.0.0.1:8000/datastores/${chatbot.datastoreId}/files/${file.id}`
        );
      }

      // 🔥 Remove associated chat history from localStorage
      localStorage.removeItem(`chat_history_${chatbot.id}`)

      // Step 3: Delete chatbot metadata (frontend state)
      deleteChatbot(chatbot.id);

      // Step 4: Delete the datastore itself
      await axios.delete(`http://127.0.0.1:8000/datastore/${chatbot.datastoreId}`);

      toast({
        title: "Chatbot & Datastore Deleted",
        description: `${chatbot.name} and all associated files have been deleted.`,
      });

      navigate('/');
    } catch (error: any) {
      console.error("Error deleting chatbot or associated data:", error);
      toast({
        title: "Error Deleting Chatbot and Data",
        description:
          error.response?.data?.detail || "An error occurred while deleting associated resources.",
        variant: "destructive",
      });
    }
  };


  const handleFileClick = async (datastoreId: number, filename: string) => {
    try {
      const response = await axios.get(
        `http://127.0.0.1:8000/datastores/${datastoreId}/files/${filename}`,
        {
          responseType: "blob",
        }
      );

      const contentType = response.headers["content-type"];
      const blob = new Blob([response.data], { type: contentType });
      const blobUrl = window.URL.createObjectURL(blob);
      window.open(blobUrl, "_blank");
    } catch (error) {
      console.error("Error opening document:", error);
      alert("Failed to open document.");
    }
  };




  const handleAddQnA = () => {
    if (!newQuestion.trim() || !newAnswer.trim()) {
      toast({
        title: "Missing Information",
        description: "Please fill in both question and answer fields.",
        variant: "destructive",
      });
      return;
    }

    addQnA(chatbot.id, {
      question: newQuestion.trim(),
      answer: newAnswer.trim(),
    });

    setNewQuestion('');
    setNewAnswer('');

    toast({
      title: "Q&A Added",
      description: "New question and answer pair has been saved.",
    });
  };



  const handleFileUpload = (file: File) => {
    addDocument(chatbot.id, file);
    setNewFile(null);

    toast({
      title: "Document Added",
      description: `${file.name} has been uploaded successfully.`,
    });
  };



  const simulateResponse = async (message: string): Promise<string> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 2000));

    // Check if there's a matching Q&A
    const matchingQnA = chatbot.qna.find(
      qa => qa.question.toLowerCase().includes(message.toLowerCase()) ||
        message.toLowerCase().includes(qa.question.toLowerCase())
    );

    if (matchingQnA) {
      return matchingQnA.answer;
    }

    // Generate a contextual response based on the chatbot's topic
    const responses = [
      `Based on my knowledge of ${chatbot.topic}, I can help you with that. However, this is a demo response. In a real implementation, I would analyze your uploaded documents to provide accurate information.`,
      `That's an interesting question about ${chatbot.topic}. In a production version, I would search through your uploaded documents to find the most relevant information.`,
      `I understand you're asking about ${chatbot.topic}. This demo shows the interface - the actual AI would process your documents and provide detailed, accurate responses.`,
      `Great question! I'm designed to assist with ${chatbot.topic}. In the full version, I would use advanced AI to analyze your documents and provide precise answers.`,
    ];

    return responses[Math.floor(Math.random() * responses.length)];
  };

  return (
    <div className="min-h-screen bg-gradient-surface">
      {/* Header */}
      <div className="border-b border-chatbot-primary/20 bg-gradient-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate('/')}
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>

              <div className="flex items-center gap-3">
                <div className="text-2xl">{chatbot.icon}</div>
                <div>
                  <h1 className="text-2xl font-bold text-foreground">{chatbot.name}</h1>
                  <p className="text-muted-foreground">{chatbot.topic}</p>
                </div>
              </div>

              <Badge variant="secondary" className="ml-4">
                Active
              </Badge>
            </div>

            <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
              <DialogTrigger asChild>
                <Button variant="destructive" size="sm">
                  <Trash2 className="h-4 w-4" />
                  Delete
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Delete Assistant</DialogTitle>
                  <DialogDescription>
                    Are you sure you want to delete "{chatbot.name}"? This action cannot be undone.
                  </DialogDescription>
                </DialogHeader>
                <div className="flex gap-3 pt-4">
                  <Button
                    variant="outline"
                    onClick={() => setShowDeleteDialog(false)}
                    className="flex-1"
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={handleDelete}
                    className="flex-1"
                  >
                    Delete Assistant
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-6">
        <Tabs defaultValue="chat" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="chat" className="flex items-center gap-2">
              <MessageSquarePlus className="h-4 w-4" />
              Chat
            </TabsTrigger>
            <TabsTrigger value="documents" className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Documents
            </TabsTrigger>
            <TabsTrigger value="manage" className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Manage
            </TabsTrigger>
          </TabsList>

          <TabsContent value="chat" className="space-y-4">
            {/* <ChatInterface
              chatbot={chatbot}
              chatbotName={chatbot.name}
              // onSendMessage={simulateResponse}
              onSendMessage={async (payload) => {
                const res = await axios.post("http://localhost:8000/query", payload);
                return res.data.answer;  // depends on your API shape
              }}
            /> */}
            <ChatInterface
              chatbot={chatbot}
              chatbotName="MyBot"
              onSendMessage={async (payload) => {
                const { question, fileId, optimizer, embeddingModel, llmModel, vectorDb, temperature, guardrailOption, tokenSize, showSources, rerankerOption } = payload;

                const response = await axios.get("http://localhost:8000/retriever/query", {
                  params: {
                    query: question,
                    query_optimizer: optimizer || "Multi Query",
                    embedding_model_name: embeddingModel || "all-MiniLM-L6-v2",
                    llm_model_name: llmModel || "llama-3.3-70b-versatile",
                    vector_db: vectorDb || "faiss",
                    file_id: fileId,
                    temperature: temperature || 0.0,
                    guardrailOption: guardrailOption,
                    token_size: tokenSize || 256,
                    sources: showSources || false,
                    rerankerOption: rerankerOption || "none" // Include sources if requested
                  },

                  // ✅ ensure arrays become file_id=12&file_id=16 instead of file_id[]=...
                  paramsSerializer: params =>
                    qs.stringify(params, { arrayFormat: "repeat" }),
                });

                return response.data || "No results found.";
              }}
            />
          </TabsContent>

          <TabsContent value="documents" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Current Documents */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Current Documents
                  </CardTitle>
                  <CardDescription>
                    Documents used to train this chatbot
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {chatbot.documents.length === 0 ? (
                    <p className="text-muted-foreground text-center py-8">
                      No documents uploaded yet
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {chatbot.documents.map((doc, index) => (
                        <div
                          key={index}
                          onClick={() => handleFileClick(chatbot.datastoreId, doc)}
                          className="flex items-start gap-3 p-3 rounded-lg bg-chatbot-surface-variant hover:bg-chatbot-surface transition cursor-pointer"
                        >
                          {/* File Icon */}
                          <FileText className="h-5 w-5 text-chatbot-primary shrink-0 mt-1" />

                          {/* File Name */}
                          <span className="flex-1 text-sm font-medium break-all leading-snug">
                            {doc}
                          </span>

                          {/* Delete Button */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation(); // Prevent file click
                              handleDeleteDocument(chatbot.id, chatbot.datastoreId, doc);
                            }}
                            className="ml-2 p-1 rounded hover:bg-red-100 text-red-500 hover:text-red-700 transition"
                            title="Delete Document"
                          >
                            <Trash className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>

                  )}
                </CardContent>
              </Card>

              {/* Add New Document */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Upload className="h-5 w-5" />
                    Add Document
                  </CardTitle>
                  <CardDescription>
                    Upload additional documents to enhance responses
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div
                      className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors duration-200 ${isDragging
                          ? "border-chatbot-primary bg-chatbot-primary/5 animate-pulse"
                          : "border-muted-foreground/25 hover:border-chatbot-primary/50"
                        }`}
                      onDragOver={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        if (!isDragging) setIsDragging(true)
                      }}
                      onDragLeave={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        setIsDragging(false)
                      }}
                      onDrop={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        setIsDragging(false)
                        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                          handleFileUpload(e.dataTransfer.files[0])
                        }
                      }}
                    >
                      <Upload
                        className="h-10 w-10 mx-auto text-muted-foreground mb-3 transition-transform duration-200"
                        style={{ transform: isDragging ? "scale(1.1)" : "scale(1)" }}
                      />
                      <div className="space-y-2">
                        <p className="text-sm font-medium">
                          {isDragging ? (
                            <span className="text-chatbot-primary font-semibold">
                              Release to upload your file
                            </span>
                          ) : (
                            <>
                              Drop your document here, or{" "}
                              <label className="text-chatbot-primary cursor-pointer hover:underline">
                                browse files
                                <input
                                  type="file"
                                  className="hidden"
                                  accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.webp"
                                  onChange={(e) => {
                                    if (e.target.files?.[0]) {
                                      handleFileUpload(e.target.files[0])
                                    }
                                  }}
                                />
                              </label>
                            </>
                          )}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Supports PDF, DOCX, TXT, and Image files (JPG, JPEG, PNG, WEBP)
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>

              </Card>
            </div>
          </TabsContent>

          <TabsContent value="manage" className="space-y-6">
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
                  {chatbot.qna.length === 0 ? (
                    <p className="text-muted-foreground text-center py-8">
                      No custom Q&A pairs added yet
                    </p>
                  ) : (
                    <div className="space-y-4 max-h-96 overflow-y-auto">
                      {chatbot.qna.map((qa) => (
                        <div
                          key={qa.id}
                          className="p-4 rounded-lg bg-chatbot-surface-variant space-y-2"
                        >
                          <div>
                            <p className="text-sm font-medium text-chatbot-primary">Q:</p>
                            <p className="text-sm">{qa.question}</p>
                          </div>
                          <div>
                            <p className="text-sm font-medium text-chatbot-accent">A:</p>
                            <p className="text-sm text-muted-foreground">{qa.answer}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Add New Q&A */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Plus className="h-5 w-5" />
                    Add Q&A Pair
                  </CardTitle>
                  <CardDescription>
                    Add custom question and answer pairs
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
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

                  <Button
                    onClick={handleAddQnA}
                    variant="chatbot"
                    className="w-full"
                    disabled={!newQuestion.trim() || !newAnswer.trim()}
                  >
                    <Plus className="h-4 w-4" />
                    Add Q&A Pair
                  </Button>
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default ChatbotDetail;