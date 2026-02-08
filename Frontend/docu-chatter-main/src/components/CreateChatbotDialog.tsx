import { useEffect, useState } from 'react';
import { Bot, Upload, FileText } from 'lucide-react';
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
import { useToast } from '@/hooks/use-toast';
import { CreateChatbotDataResponse, CreateDatastoreData } from '@/types/chatbot';
import { useChatbots } from '@/hooks/useChatbots';
import axios from 'axios';
import { useNavigate } from "react-router-dom"; // for redirection
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { fetchDatastores } from '@/pages/DatastoreDashboard';
import { API_BASE_URL } from '@/constants';

interface CreateChatbotDialogProps {
  onCreateChatbot: (data: CreateChatbotDataResponse) => void
  children: React.ReactNode;
}

export const CreateChatbotDialog = ({ onCreateChatbot, children }: CreateChatbotDialogProps) => {
  const [open, setOpen] = useState(false);
  const [datastores, setDatastores] = useState<CreateDatastoreData[]>([]);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    datastore_id: ''
  });
  const [file, setFile] = useState<File | null>(null);
  const [files, setFiles] = useState([]);

  const [dragActive, setDragActive] = useState(false);
  const { toast } = useToast();
  // const { addDocument } = useChatbots(); // Removed unused destructuring if existing
  const [loading, setLoading] = useState(false);
  const [url, setUrl] = useState<string>("")

  useEffect(() => {
    const fetchStore = async () => {
      setDatastores(await fetchDatastores());
    }
    fetchStore()
  }, []);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setFormData({ name: '', description: '', datastore_id: '' });
      setFiles([]);
    }
  }, [open]);

  interface ChatbotApiData {
    name: string;
    description: string;
    datastore_id: string;
  }

  const createChatbotApiCall = async (data: ChatbotApiData) => {
    
    const response = await axios.post(`${API_BASE_URL}/rag/createAssistant/`, {
      name: data.name,
      description: data.description,
      datastore_id: Number(data.datastore_id),
    });
    return response.data;
  };

  // ... (uploadFileToDatastore and scrapeWebsite commented out code) ...

  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim() || !formData.description.trim() || !formData.datastore_id.trim()) {
      toast({
        title: "Missing Information",
        description: "Please fill in both name, description & datastore fields.",
        variant: "destructive",
      });
      return;
    }

    // Prepare data
    const chatbotData: ChatbotApiData = {
      name: formData.name.trim(),
      description: formData.description.trim(),
      datastore_id: formData.datastore_id.trim()
    };

    setLoading(true);

    try {
      const created = await createChatbotApiCall(chatbotData);

      onCreateChatbot({
        id: created.id,
        name: created.name,
        description: created.description,
        datastore_id: created.datastore_id,
        created_at: created.created_at
      });

      // Reset form and state
      setFormData({ name: "", description: "", datastore_id: "" });
      setFiles([]);
      setOpen(false);

      // ✅ Redirect to chatbot detail page
      navigate(`/`);
      toast({
        title: "Chatbot Created! 🎉",
        description: `${chatbotData.name} is ready to assist with ${chatbotData.description}.`,
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error?.response?.data?.detail || "Something went wrong.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
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
      <DialogTrigger asChild>{children}</DialogTrigger>
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
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
                className="mt-1.5"
              />
            </div>

            <div>
              <Label htmlFor="description" className="text-sm font-medium">
                Description
              </Label>
              <Input
                id="description"
                placeholder="e.g., Tax Policies 2024"
                value={formData.description}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, description: e.target.value }))
                }
                className="mt-1.5"
              />
            </div>

            <div>
              <Label htmlFor="category" className="text-sm font-medium">
                Datastore
              </Label>
              <Select
                value={formData.datastore_id}
                onValueChange={(value) =>
                  setFormData((prev) => ({ ...prev, datastore_id: value }))
                }
              >
                <SelectTrigger className="mt-1.5 w-full">
                  <SelectValue placeholder="Select a datastore" />
                </SelectTrigger>
                <SelectContent>
                  {datastores.map((ds) => (
                    <SelectItem key={ds.id} value={String(ds.id)}>
                      {ds.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
              {loading ? "Creating..." : "Create assistant"}
            </Button>
          </div>
        </form>

      </DialogContent>
    </Dialog>
  );
};