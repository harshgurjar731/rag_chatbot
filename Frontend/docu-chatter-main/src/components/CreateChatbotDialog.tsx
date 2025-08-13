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
  const [dragActive, setDragActive] = useState(false);
  const { toast } = useToast();
  const { addDocument } = useChatbots();
  const [loading, setLoading] = useState(false);


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

      if (file) {
        await uploadFileToDatastore(created.id, file);
      }

      // onCreateChatbot(created);
      console.log(created.id)
      const x = onCreateChatbot({
        id: created.id,
        name: created.name,
        topic: created.description,
        document: file || undefined,
      });

      // console.log(x.id)
      // await updateChatbotIdApiCall(created.id,x.id);



      setFormData({ name: '', topic: '' });
      setFile(null);
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
    }
    finally {
      setLoading(false); // ✅ END LOADING
    }
  };


  // const handleSubmit = (e: React.FormEvent) => {
  //   e.preventDefault();

  //   if (!formData.name.trim() || !formData.topic.trim()) {
  //     toast({
  //       title: "Missing Information",
  //       description: "Please fill in both name and topic fields.",
  //       variant: "destructive",
  //     });
  //     return;
  //   }

  //   onCreateChatbot({
  //     name: formData.name.trim(),
  //     topic: formData.topic.trim(),
  //     document: file || undefined,
  //   });

  //   // Reset form
  //   setFormData({ name: '', topic: '' });
  //   setFile(null);
  //   setOpen(false);

  //   toast({
  //     title: "Chatbot Created! 🎉",
  //     description: `${formData.name} is ready to assist with ${formData.topic}.`,
  //   });
  // };

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

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (isValidFileType(droppedFile)) {
        setFile(droppedFile);
      } else {
        toast({
          title: "Invalid File Type",
          description: "Please upload a PDF, DOCX, or TXT file.",
          variant: "destructive",
        });
      }
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (isValidFileType(selectedFile)) {
        setFile(selectedFile);
      } else {
        toast({
          title: "Invalid File Type",
          description: "Please upload a PDF, DOCX, or TXT file.",
          variant: "destructive",
        });
      }
    }
  };

  const isValidFileType = (file: File) => {
    const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
    return validTypes.includes(file.type) || file.name.endsWith('.txt') || file.name.endsWith('.pdf') || file.name.endsWith('.docx');
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px] bg-gradient-card border-chatbot-primary/20">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Bot className="h-6 w-6 text-chatbot-primary" />
            Create New Chatbot
          </DialogTitle>
          <DialogDescription>
            Build a specialized AI assistant for your specific topic and documents.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="name" className="text-sm font-medium">
                Chatbot Name
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
                Topic/Domain
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
                Policy Document (Optional)
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
                <CardContent className="p-6">
                  {file ? (
                    <div className="flex items-center gap-3">
                      <FileText className="h-8 w-8 text-chatbot-primary" />
                      <div>
                        <p className="font-medium">{file.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setFile(null)}
                        className="ml-auto"
                      >
                        Remove
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center">
                      <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                      <div className="space-y-2">
                        <p className="text-sm font-medium">
                          Drop your document here, or{' '}
                          <label className="text-chatbot-primary cursor-pointer hover:underline">
                            browse files
                            <input
                              type="file"
                              className="hidden"
                              accept=".pdf,.docx,.txt"
                              onChange={handleFileInput}
                            />
                          </label>
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Supports PDF, DOCX, and TXT files
                        </p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
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
              {loading ? "Creating..." : "Create Chatbot"}
              {/* Create Chatbot */}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};