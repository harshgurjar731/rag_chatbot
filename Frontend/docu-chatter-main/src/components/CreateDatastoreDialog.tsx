import { useState } from 'react';
import { Bot, Upload, FileText, Sparkles, DatabaseIcon } from 'lucide-react';
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
import { CreateDatastoreData } from '@/types/chatbot';
import { useChatbots } from '@/hooks/useChatbots';
import axios from 'axios';
import { useNavigate } from "react-router-dom"; // for redirection
import { API_BASE_URL } from '@/constants';

interface CreateDatastoreDialogProps {
  onCreateDatastore: (data: CreateDatastoreData) => void
  children: React.ReactNode;
}

export const CreateDatastoreDialog = ({ onCreateDatastore, children }: CreateDatastoreDialogProps) => {
  const [open, setOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
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


  const createDatastoreApiCall = async (data: { name: string; description: string }) => {
    console.log("API_Base_URL", API_BASE_URL)
    const response = await axios.post(`${API_BASE_URL}/ingestion/createDatastore`, {
      name: data.name,
      description: data.description,
    });
    console.log("Create Datastore Response:", response.data);
    console.log("Create Datastore Response Date:", response.data.created_at);
    return {id: response.data.id, name: response.data.name, description: response.data.description, updatedAt: response.data.created_at}; // { id, name, description }
  };



//   const uploadFileToDatastore = async (datastoreId: number, file: File) => {
//     const formData = new FormData();
//     formData.append("file", file);

//     const response = await axios.post(
//       `http://172.200.163.232:8000/datastores/${datastoreId}/upload`,
//       formData,
//       {
//         headers: {
//           "Content-Type": "multipart/form-data",
//         },
//       }
//     );

//     return response.data; // { message, file_id, filename }
//   };

//   interface ScrapeResponse {
//     url: string;
//     file_path: string;
//     message: string;
//   }

//   const scrapeWebsite = async (datastoreId: number, url: string) => {
//     try {
//       const { data } = await axios.post(
//         `http://172.200.163.232:8000/urlscraper/${datastoreId}`,
//         {}, // empty body
//         { params: { url } } // URL as query param
//       );
//       return data; // { url, file_path, message }
//     } catch (err: any) {
//       console.error("Error scraping website:", err.response?.data || err.message);
//       throw err;
//     }
//   };



  const navigate = useNavigate();
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim() || !formData.description.trim()) {
      toast({
        title: "Missing Information",
        description: "Please fill in both name and description fields.",
        variant: "destructive",
      });
      return;
    }

    const datastoreData = {
      name: formData.name.trim(),
      description: formData.description.trim(),
    };

    setLoading(true); // ✅ START LOADING

    try {
      const created = await createDatastoreApiCall(datastoreData);

      // ✅ Upload all selected files, if any
    //   if (files && files.length > 0) {
    //     for (const file of files) {
    //       await uploadFileToDatastore(created.id, file);
    //     }
    //   }

    //   // ✅ Scrape website if provided
    //   if (url) {
    //     await scrapeWebsite(created.id, url);
    //   }

      const x = onCreateDatastore({
        id: created.id,
        name: created.name,
        description: created.description,
        documents: undefined,
        updatedAt: created.updatedAt,
      });

      // Reset form and state
      setFormData({ name: "", description: "" });
      setFiles([]);
      setOpen(false);

      // ✅ Redirect to chatbot detail page
      navigate(`/datastore2`);
      toast({
        title: "Datastore Created! 🎉",
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
    <Dialog open={open} onOpenChange={(isOpen) => {
        setOpen(isOpen);
        if (!isOpen) {
          setFormData({ name: "", description: "" });
        }
    }}>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px] bg-gradient-card border-chatbot-primary/20 overflow-y-auto max-h-[100vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <DatabaseIcon className="h-6 w-6 text-chatbot-primary" />
            Create New Datastore
          </DialogTitle>
          <DialogDescription>
            Fill in the details below to create a new datastore.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="name" className="text-sm font-medium">
                Datastore Name
              </Label>
              <Input
                id="name"
                placeholder="Enter datastore name"
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                className="mt-1.5"
              />
            </div>

            <div>
              <Label htmlFor="description" className="text-sm font-medium">
                Description
              </Label>
              <Input
                id="description"
                placeholder="Brief description of the datastore"
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                className="mt-1.5"
              />
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setOpen(false)
                setFormData({ name: "", description: "" })
            }}
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
              {loading ? "Creating..." : "Create datastore"}
              {/* Create Chatbot */}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};