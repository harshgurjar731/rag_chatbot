import { useEffect, useState } from 'react';
import { Bot, Upload, FileText, Sparkles, ArrowLeft, Plus, Trash2 } from 'lucide-react';
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
import { Switch } from "@/components/ui/switch"
import { fetchDatastores } from '@/pages/DatastoreDashboard';

interface CreateChatbotDialogProps {
  onCreateChatbot: (data: CreateChatbotDataResponse) => void
  children: React.ReactNode;
}

interface IntentData {
  title: string;
  description: string;
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

  // const handleFileInput = (e) => {
  //   const selectedFiles = Array.from(e.target.files);
  //   setFiles((prev) => [...prev, ...selectedFiles]);
  // };

  const [dragActive, setDragActive] = useState(false);
  const { toast } = useToast();
  const { addDocument } = useChatbots();
  const [loading, setLoading] = useState(false);
  const [url, setUrl] = useState<string>("")

  // New State for "Add Intent" feature
  const [addIntentEnabled, setAddIntentEnabled] = useState(false);
  const [step, setStep] = useState(1);
  const [intents, setIntents] = useState<IntentData[]>([{ title: '', description: '' }]);

  useEffect(() => {
    const fetchStore = async () => {
      setDatastores(await fetchDatastores());
    }
    fetchStore()
  }, []);

  // Reset state when dialog closes
  useEffect(() => {
    if (!open) {
      setStep(1);
      setAddIntentEnabled(false);
      setFormData({ name: '', description: '', datastore_id: '' });
      setIntents([{ title: '', description: '' }]);
      setFiles([]);
    }
  }, [open]);

  interface ChatbotApiData {
    name: string;
    description: string;
    datastore_id: string;
    intents?: IntentData[];
  }

  const createChatbotApiCall = async (data: ChatbotApiData) => {
    const response = await axios.post('http://127.0.0.1:8000/rag/createAssistant/', {
      name: data.name,
      description: data.description,
      datastore_id: Number(data.datastore_id),
      intents: data.intents
    });
    return response.data; // { id, name, description, intents }
  };

  // ... (uploadFileToDatastore and scrapeWebsite commented out code) ...

  const navigate = useNavigate();

  const handleNext = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.description.trim() || !formData.datastore_id.trim()) {
      toast({
        title: "Missing Information",
        description: "Please fill in both name, description & datastore fields.",
        variant: "destructive",
      });
      return;
    }
    setStep(2);
  };

  const handleAddIntent = () => {
    setIntents([...intents, { title: '', description: '' }]);
  };

  const handleRemoveIntent = (index: number) => {
    const newIntents = intents.filter((_, i) => i !== index);
    setIntents(newIntents);
  };

  const handleIntentChange = (index: number, field: keyof IntentData, value: string) => {
    const newIntents = [...intents];
    newIntents[index][field] = value;
    setIntents(newIntents);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // If "Add Intent" is enabled and we are on step 1, go to step 2 instead of submitting
    if (addIntentEnabled && step === 1) {
      handleNext(e);
      return;
    }

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

    if (addIntentEnabled) {
      // Filter out empty intents if necessary, or just send them
      // For now, let's send them all, maybe filter out completely empty ones
      const validIntents = intents.filter(i => i.title.trim() !== '' || i.description.trim() !== '');
      if (validIntents.length > 0) {
        chatbotData.intents = validIntents;
      }
    }

    setLoading(true); // ✅ START LOADING

    try {
      const created = await createChatbotApiCall(chatbotData);

      const x = onCreateChatbot({
        id: created.id,
        name: created.name,
        description: created.description,
        datastore_id: created.datastore_id,
        created_at: created.created_at,
        intents: created.intents
      });

      // Reset form and state
      setFormData({ name: "", description: "", datastore_id: "" });
      setFiles([]);
      setOpen(false);
      setStep(1);

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
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-[500px] bg-gradient-card border-chatbot-primary/20 overflow-y-auto max-h-[100vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            {step === 2 && (
              <Button variant="ghost" size="icon" className="h-6 w-6 mr-1" onClick={() => setStep(1)}>
                <ArrowLeft className="h-4 w-4" />
              </Button>
            )}
            {step === 1 ? (
              <>
                <Bot className="h-6 w-6 text-chatbot-primary" />
                Create New Assistant
              </>
            ) : (
              <>
                <Sparkles className="h-6 w-6 text-chatbot-primary" />
                Add Intent
              </>
            )}
          </DialogTitle>
          <DialogDescription>
            {step === 1
              ? "Build a specialized AI assistant for your specific topic and documents."
              : "Define intents for your assistant. Add titles and descriptions."
            }
          </DialogDescription>
        </DialogHeader>

        {step === 1 ? (
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

              {/* Add Intent Toggle */}
              <div className="flex items-center space-x-2 pt-2">
                <Switch
                  id="add-intent"
                  checked={addIntentEnabled}
                  onCheckedChange={setAddIntentEnabled}
                  className="data-[state=checked]:bg-chatbot-primary data-[state=unchecked]:bg-slate-300 dark:data-[state=unchecked]:bg-slate-700"
                />
                <Label htmlFor="add-intent">Add Intent</Label>
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
                {/* Dynamically change button text */}
                {loading
                  ? "Creating..."
                  : addIntentEnabled
                    ? "Next"
                    : "Create assistant"}
              </Button>
            </div>
          </form>
        ) : (
          <div className="space-y-6">
            <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
              {intents.map((intent, index) => (
                <div key={index} className="p-4 border rounded-lg bg-card/50 relative group">
                  <div className="space-y-3">
                    <div>
                      <Label htmlFor={`intent-title-${index}`} className="text-xs font-medium text-muted-foreground">
                        Intent Title
                      </Label>
                      <Input
                        id={`intent-title-${index}`}
                        placeholder="e.g., Check Refund Status"
                        value={intent.title}
                        onChange={(e) => handleIntentChange(index, 'title', e.target.value)}
                        className="mt-1"
                      />
                    </div>
                    <div>
                      <Label htmlFor={`intent-desc-${index}`} className="text-xs font-medium text-muted-foreground">
                        Description
                      </Label>
                      <Input
                        id={`intent-desc-${index}`}
                        placeholder="e.g., Guide users on finding their refund status"
                        value={intent.description}
                        onChange={(e) => handleIntentChange(index, 'description', e.target.value)}
                        className="mt-1"
                      />
                    </div>
                  </div>

                  {intents.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute top-2 right-2 h-6 w-6 text-muted-foreground hover:text-destructive"
                      onClick={() => handleRemoveIntent(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}

              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full border-dashed"
                onClick={handleAddIntent}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Another Intent
              </Button>
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setStep(1)}
                className="flex-1"
              >
                Back
              </Button>
              <Button
                type="button"
                variant="chatbot"
                className="flex-1"
                disabled={loading}
                onClick={handleSubmit}
              >
                {loading ? "Creating..." : "Create assistant"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};