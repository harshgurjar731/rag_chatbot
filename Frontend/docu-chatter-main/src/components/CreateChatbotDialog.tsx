import { useState } from 'react';
import { Bot, Upload, FileText, Sparkles } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { CreateChatbotData } from '@/types/chatbot';
import { useChatbots } from '@/hooks/useChatbots';
import axios from 'axios';
import { useNavigate } from "react-router-dom"; // for redirection

interface CreateChatbotDialogProps {
  onCreateChatbot: (data: CreateChatbotData) => void
  children: React.ReactNode;
}

export const CreateChatbotDialog = ({ onCreateChatbot, children }: CreateChatbotDialogProps) => {
  const [open, setOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    topic: '',
  });
  const [file, setFile] = useState<File | null>(null);
  const [files, setFiles] = useState([]);

  // const handleFileInput = (e) => {
  //   const selectedFiles = Array.from(e.target.files);
  //   setFiles((prev) => [...prev, ...selectedFiles]);
  // };

  const [dragActive, setDragActive] = useState(false);
  const { toast } = useToast();
  const { addDocument } = useChatbots();
  const [loading, setLoading] = useState(false);
  const [url, setUrl] = useState<string>("")


  const createDatastoreApiCall = async (data: { name: string; topic: string }) => {
    const response = await axios.post('http://127.0.0.1:8000/datastore/', {
      name: data.name,
      description: data.topic,
    });
    return response.data; // { id, name, description }
  };



  const uploadFileToDatastore = async (datastoreId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await axios.post(
      `http://127.0.0.1:8000/datastores/${datastoreId}/upload`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );

    return response.data; // { message, file_id, filename }
  };

  interface ScrapeResponse {
    url: string;
    file_path: string;
    message: string;
  }

  const scrapeWebsite = async (datastoreId: number, url: string) => {
    try {
      const { data } = await axios.post(
        `http://127.0.0.1:8000/urlscraper/${datastoreId}`,
        {}, // empty body
        { params: { url } } // URL as query param
      );
      return data; // { url, file_path, message }
    } catch (err: any) {
      console.error("Error scraping website:", err.response?.data || err.message);
      throw err;
    }
  };



  const navigate = useNavigate();
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim() || !formData.topic.trim()) {
      toast({
        title: "Missing Information",
        description: "Please fill in both name and topic fields.",
        variant: "destructive",
      });
      return;
    }

    const chatbotData = {
      name: formData.name.trim(),
      topic: formData.topic.trim(),
    };

    setLoading(true); // ✅ START LOADING

    try {
      const created = await createDatastoreApiCall(chatbotData);

      // ✅ Upload all selected files, if any
      if (files && files.length > 0) {
        for (const file of files) {
          await uploadFileToDatastore(created.id, file);
        }
      }

      // ✅ Scrape website if provided
      if (url) {
        await scrapeWebsite(created.id, url);
      }

      const x = onCreateChatbot({
        id: created.id,
        name: created.name,
        topic: created.description,
        documents: files || undefined,
      });

      // Reset form and state
      setFormData({ name: "", topic: "" });
      setFiles([]);
      setOpen(false);

      // ✅ Redirect to chatbot detail page
      navigate(`/`);
      toast({
        title: "Chatbot Created! 🎉",
        description: `${chatbotData.name} is ready to assist with ${chatbotData.topic}.`,
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error?.response?.data?.detail || "Something went wrong.",
        variant: "destructive",
      });
    } finally {
      setLoading(false); // ✅ END LOADING
    }
  };


  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
  e.preventDefault();
  e.stopPropagation();
  setDragActive(false);

  if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    const droppedFiles = Array.from(e.dataTransfer.files);
    const validFiles: File[] = [];
    const invalidFiles: string[] = [];

    droppedFiles.forEach((file) => {
      if (isValidFileType(file)) {
        validFiles.push(file);
      } else {
        invalidFiles.push(file.name);
      }
    });

    if (validFiles.length > 0) {
      setFiles((prev) => [...prev, ...validFiles]);
    }

    if (invalidFiles.length > 0) {
      toast({
        title: "Invalid File Type",
        description: `The following files are not supported: ${invalidFiles.join(", ")}. 
          Please upload PDF, DOCX, TXT, or image files (JPG, JPEG, PNG, WEBP).`,
        variant: "destructive",
      });
    }
  }
};


  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFiles = Array.from(e.target.files);
      const validFiles: File[] = [];
      const invalidFiles: string[] = [];

      selectedFiles.forEach((file) => {
        if (isValidFileType(file)) {
          validFiles.push(file);
        } else {
          invalidFiles.push(file.name);
        }
      });

      if (validFiles.length > 0) {
        setFiles((prev) => [...prev, ...validFiles]);
      }

      if (invalidFiles.length > 0) {
        toast({
          title: "Invalid File Type",
          description: `The following files are not supported: ${invalidFiles.join(", ")}. 
          Please upload PDF, DOCX, TXT, or image files (JPG, JPEG, PNG, WEBP).`,
          variant: "destructive",
        });
      }

      // Clear the input value so selecting the same file again triggers onChange
      e.target.value = "";
    }
  };


  const isValidFileType = (file: File) => {
    const validTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
      'image/jpeg',
      'image/png',
      'image/webp'
    ];

    return (
      validTypes.includes(file.type) ||
      file.name.toLowerCase().endsWith('.txt') ||
      file.name.toLowerCase().endsWith('.pdf') ||
      file.name.toLowerCase().endsWith('.docx') ||
      file.name.toLowerCase().endsWith('.jpg') ||
      file.name.toLowerCase().endsWith('.jpeg') ||
      file.name.toLowerCase().endsWith('.png') ||
      file.name.toLowerCase().endsWith('.webp')
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px] bg-gradient-card border-chatbot-primary/20 overflow-y-auto max-h-[100vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Bot className="h-6 w-6 text-chatbot-primary" />
            Create New Assistant
          </DialogTitle>
          <DialogDescription>
            Build a specialized AI assistant for your specific topic and documents.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="name" className="text-sm font-medium">
                Assistant Name
              </Label>
              <Input
                id="name"
                placeholder="e.g., Income Tax Assistant"
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                className="mt-1.5"
              />
            </div>

            <div>
              <Label htmlFor="topic" className="text-sm font-medium">
                Description
              </Label>
              <Input
                id="topic"
                placeholder="e.g., Tax Policies 2024"
                value={formData.topic}
                onChange={(e) => setFormData(prev => ({ ...prev, topic: e.target.value }))}
                className="mt-1.5"
              />
            </div>

            <div>
              <Label className="text-sm font-medium">
                Document (Optional)
              </Label>
              <Card
                className={`mt-1.5 border-2 border-dashed transition-colors ${dragActive
                  ? 'border-chatbot-primary bg-chatbot-primary/5'
                  : 'border-muted-foreground/25 hover:border-chatbot-primary/50'
                  }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <CardContent className="p-6 overflow-y-auto max-h-60">
                  {files && files.length > 0 ? (
                    <div className="space-y-3">
                      {files.map((file, index) => (
                        <div key={index} className="flex items-center gap-3 border p-2 rounded-lg">
                          <FileText className="h-8 w-8 text-chatbot-primary" />
                          <div className="flex-1">
                            <p className="font-medium">{file.name}</p>
                            <p className="text-sm text-muted-foreground">
                              {(file.size / 1024 / 1024).toFixed(2)} MB
                            </p>
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              const updatedFiles = files.filter((_, i) => i !== index);
                              setFiles(updatedFiles);
                            }}
                          >
                            Remove
                          </Button>
                        </div>
                      ))}

                      <div className="text-center">
                        <label className="text-chatbot-primary cursor-pointer hover:underline">
                          + Add more files
                          <input
                            type="file"
                            multiple
                            className="hidden"
                            accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.webp"
                            onChange={handleFileInput}
                          />
                        </label>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center">
                      <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                      <div className="space-y-2">
                        <p className="text-sm font-medium">
                          Drop your documents here, or{' '}
                          <label className="text-chatbot-primary cursor-pointer hover:underline">
                            browse files
                            <input
                              type="file"
                              multiple
                              className="hidden"
                              accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.webp"
                              onChange={handleFileInput}
                            />
                          </label>
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Supports multiple PDF, DOCX, TXT, and Image files (JPG, JPEG, PNG, WEBP)
                        </p>
                      </div>
                    </div>
                  )}
                </CardContent>

              </Card>
            </div>
            <div>
              <Label htmlFor="url" className="text-sm font-medium">
                Website URL
              </Label>
              <Input
                id="url"
                type="url"
                placeholder="e.g., https://example.com/"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="mt-1.5"
              />
            </div>

          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="chatbot"
              className="flex-1"
              disabled={loading}
            >
              <Sparkles className="h-4 w-4" />
              {loading ? "Creating..." : "Create Assistant"}
              {/* Create Chatbot */}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};