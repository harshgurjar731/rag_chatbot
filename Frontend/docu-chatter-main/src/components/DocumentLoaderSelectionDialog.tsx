import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Search, X } from "lucide-react";
import { DocumentLoaderConfigForm } from "./DocumentLoaderConfigForm";
import { DocumentObj } from "@/pages/DatastoreConfigDetail";

const loaderTypes = [
  // { id: "airtable", name: "Airtable", icon: "📊" },
  // { id: "api", name: "API Loader", icon: "🔌" },
  // { id: "apify", name: "Apify Website Content Crawler", icon: "🕷️" },
  // { id: "brave", name: "BraveSearch API Document Loader", icon: "🦁" },
  // { id: "cheerio", name: "Cheerio Web Scraper", icon: "🌐" },
  // { id: "confluence", name: "Confluence", icon: "📘" },
  { id: "csv", name: "Csv File", icon: "📊" },
  // { id: "custom", name: "Custom Document Loader", icon: "⚙️" },
  { id: "docx", name: "Docx File", icon: "📄" },
  // { id: "epub", name: "Epub File", icon: "📖" },
  // { id: "figma", name: "Figma", icon: "🎨" },
  { id: "pdf", name: "PDF File", icon: "📁" },
  { id: "img", name: "Image Loader", icon: "🎨" },
];

interface DocumentLoaderSelectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  datastoreId?: number;
  selectedDocument?: DocumentObj
}

export const DocumentLoaderSelectionDialog = ({
  open,
  onOpenChange,
  datastoreId,
  selectedDocument,
}: DocumentLoaderSelectionDialogProps) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLoader, setSelectedLoader] = useState<string | null>(null);

  const filteredLoaders = loaderTypes.filter((loader) =>
    loader.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  useEffect(() => {
    console.log("Datastore ID in DocumentLoaderSelectionDialog:", datastoreId);
  }, [datastoreId]);

  useEffect(() => {
    console.log("Calling setSelectedLoader ")
    if(selectedDocument){
      setSelectedLoader(selectedDocument.loaderType)
    }
  }, [selectedDocument])

  const handleLoaderSelect = (loaderId: string) => {
    setSelectedLoader(loaderId);
  };

  const handleBack = () => {
    setSelectedLoader(null);
  };

  if (selectedLoader) {
    return (
      <DocumentLoaderConfigForm
        open={open}
         onOpenChange={async(open) => {
          if(!open){
            setSelectedLoader(null)
          }  
          onOpenChange(open)
        }}
        // onOpenChange={onOpenChange}
        loaderType={selectedLoader}
        datastoreId={datastoreId}
        onBack={handleBack}
        selectedDocument={selectedDocument}
      />
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-2xl">Select Document Loader</DialogTitle>
        </DialogHeader>
        
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 pr-10"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-3 gap-4 pb-4">
            {filteredLoaders.map((loader) => (
              <button
                key={loader.id}
                onClick={() => handleLoaderSelect(loader.id)}
                className="flex items-center gap-3 p-4 rounded-lg border bg-card hover:bg-accent hover:border-primary transition-all text-left"
              >
                <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center text-2xl">
                  {loader.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{loader.name}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
