import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, MoreHorizontal, Settings, Trash, RefreshCw, Search, Edit, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useChatbots } from "@/hooks/useChatbots";
import { DocumentLoaderSelectionDialog } from "@/components/DocumentLoaderSelectionDialog";
import { EmbeddingConfigWizard } from "@/components/EmbeddingConfigWizard";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CreateDatastoreData } from "@/types/chatbot";
import axios from "axios";

export interface DocumentObj {
  id: string;
  chunkOverlap: number;
  chunkSize: number;
  datastore_id: number;
  filePath: string | null;
  filename: string;
  loaderType: string;
  textSplitMethod: string;
  uploaded_at: string;
  insert_vector_status: boolean;
  chunkCount: number
}

export const DatastoreConfigDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { getChatbot, refetchChatbots } = useChatbots();
  const [datastore, setDatastore] = useState<any>(null);
  const [documents, setDocuments] = useState<DocumentObj[]>([]);
  const [showLoaderDialog, setShowLoaderDialog] = useState(false);
  const [showEmbeddingWizard, setShowEmbeddingWizard] = useState(false);
  const [shouldUpsert, setShouldUpsert] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState<DocumentObj>();
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing">("idle");

  async function fetchDocuments(datastore_id: number) {
      try {
        const response = await axios.get(`http://127.0.0.1:8000/ingestion/datastore/${id}/documents`);
        var documentFromApi: DocumentObj[] = [];
        response.data.forEach((doc: any) => {
          const document = {
            id: doc.id,
            chunkOverlap: doc.chunkOverlap,
            chunkSize: doc.chunkSize,
            datastore_id: doc.datastore_id,
            filePath: doc.filePath,
            filename: doc.filename,
            loaderType: doc.loaderType,
            textSplitMethod: doc.textSplitMethod,
            uploaded_at: doc.uploaded_at,
            insert_vector_status: doc.insert_vector_status,
            chunkCount: doc.chunk_count ?? 0
          };
          documentFromApi.push(document)
        });
        console.log("Received details:", documentFromApi)
        setDocuments(documentFromApi)
      } catch (error) {
        console.error('Error fetching documents:', error);
      }
  }

  const handleLoaderOpenChange = async(open: boolean) => {
    setShowLoaderDialog(open)
    if (!open) {
      await fetchDocuments(datastore.id)
    }
  }

  useEffect(() => {
    const fetchedDatastores = JSON.parse(localStorage.getItem("createdDataStores")
      || "[]");
    const fetchedDatastore = fetchedDatastores.find((ds: CreateDatastoreData) => ds.id === Number(id))
    setDatastore(fetchedDatastore)
    fetchDocuments(fetchedDatastore.id)
  }, [id]);

  const rowSelected = (id: string) => {
    console.log("Row Selected")
    setSelectedDocument(documents.find(doc => doc.id === id))
  }

  const deleteDoc = async(id: string) => {
    console.log("Delete Row ", id) 
    const response = await axios.post(`http://127.0.0.1:8000/ingestion/deleteDocument/${id}`);
    await fetchDocuments(datastore.id);
  }

  useEffect(() => {
    if(selectedDocument) {
      setShowLoaderDialog(true)
    }
  }, [selectedDocument])

  const handleSync = async () => {
    setSyncStatus("syncing");
    await refetchChatbots();
    setTimeout(() => setSyncStatus("idle"), 1000);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate("/datastore2")}
                // className="text-secondary-foreground hover:bg-primary/90"
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold text-foreground">
                  {datastore?.name || "Loading..."}
                </h1>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="chatbot"
                onClick={() => setShowLoaderDialog(true)}
                // className="bg-primary hover:bg-primary/90"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Document
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline">
                    More Actions
                    <MoreHorizontal className="h-4 w-4 ml-2" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuItem>
                    <Settings className="h-4 w-4 mr-2" />
                    View & Edit Chunks
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => {
                      setShouldUpsert(true);
                      setShowEmbeddingWizard(true);
                    }}
                  >
                    <Settings className="h-4 w-4 mr-2" />
                    Upsert All Chunks
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => {
                      setShouldUpsert(false);
                      setShowEmbeddingWizard(true);
                    }}
                  >
                    <Search className="h-4 w-4 mr-2" />
                    Retrieval Query
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleSync}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Refresh
                  </DropdownMenuItem>
                  <DropdownMenuItem className="text-destructive">
                    <Trash className="h-4 w-4 mr-2" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="container mx-auto px-6 py-6">
        {documents.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[500px] text-center">
            <div className="mb-6 relative">
              <div className="w-24 h-24 bg-muted rounded-lg flex items-center justify-center">
                <div className="absolute -right-2 -bottom-2 w-16 h-16 bg-primary/20 rounded-lg" />
                <div className="absolute -right-4 -bottom-4 w-12 h-12 bg-primary/30 rounded-lg" />
                <svg
                  className="w-12 h-12 text-primary relative z-10"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
            </div>
            <h2 className="text-2xl font-semibold mb-3">
              No Document Added Yet
            </h2>
            <Button
              variant="chatbot"
              onClick={() => setShowLoaderDialog(true)}
              // className="mt-4 bg-primary hover:bg-primary/90"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Document
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {syncStatus === "syncing" && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Badge variant="secondary" className="bg-green-100 text-green-700">
                  <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                  SYNC
                </Badge>
              </div>
            )}
            <div className="bg-card rounded-lg border">
              <div className="grid grid-cols-12 gap-4 px-6 py-3 border-b bg-muted/50 font-medium text-sm">
                <div className="col-span-4">File</div>
                <div className="col-span-1">Loader </div>
                <div className="col-span-3">Splitter</div>
                <div className="col-span-1 text-center">Chunk Count</div>
                <div className="col-span-1 text-center">Chunk Size</div>
                <div className="col-span-1 text-center">Chunk Overlap</div>
                <div className="col-span-1 text-center"></div>
              </div>
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="grid grid-cols-12 gap-4 px-6 py-4 border-b last:border-b-0 hover:bg-muted/50 transition-colors"
                  onClick={() => rowSelected(doc.id)}
                >
                  <div className="col-span-4 flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${
                        doc.insert_vector_status ? "bg-green-500" : "bg-gray-500"
                      }`} />
                    <span className="text-sm overflow-hidden text-ellipsis whitespace-nowrap">{doc.filename}</span>
                  </div>
                  <div className="col-span-1 text-sm">{doc.loaderType}</div>
                  <div className="col-span-3 text-sm">{doc.textSplitMethod}</div>
                  <div className="col-span-1 flex justify-center">
                    <Badge variant="outline">{doc.chunkCount}</Badge>
                  </div>
                  <div className="col-span-1 flex justify-center ">
                    <Badge variant="outline">{doc.chunkSize}</Badge>
                  </div>
                  <div className="col-span-1 flex justify-center ">
                    <Badge variant="outline">{doc.chunkOverlap}</Badge>
                  </div>
                  <div className="col-span-1 flex justify-center">
                    <button
                      className="hover:text-chatbot-primary/15"
                      onClick={(e) => {
                        e.stopPropagation(); // Prevent triggering row click
                        deleteDoc(doc.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
          // <div className="space-y-4">
          //   {syncStatus === "syncing" && (
          //     <div className="flex items-center gap-2 text-sm text-muted-foreground">
          //       <Badge
          //         variant="secondary"
          //         className="bg-green-100 text-green-700"
          //       >
          //         <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
          //         SYNC
          //       </Badge>
          //     </div>
          //   )}

          //   <div className="bg-card rounded-lg border">
          //     <div className="grid grid-cols-13 gap-4 px-6 py-3 border-b bg-muted/50 font-medium text-sm">
          //       <div className="col-span-4">File</div>
          //       <div className="col-span-1">Loader</div>
          //       <div className="col-span-3">Splitter</div>
          //       <div className="col-span-2">Chunk Size</div>
          //       <div className="col-span-2">Chunk Overlap</div>
          //       <div className="col-span-1 text-center">Delete</div>
          //     </div>

          //     {documents.map((doc) => (
          //       <div
          //         key={doc.id}
          //         className="grid grid-cols-13 gap-4 px-6 py-4 border-b last:border-b-0 hover:bg-muted/50 transition-colors"
          //         onClick={() => rowSelected(doc.id)}
          //       >
          //         <div className="col-span-4 flex items-center gap-2">
          //           <div className="w-2 h-2 bg-green-500 rounded-full" />
          //           <span className="text-sm">{doc.filename}</span>
          //         </div>

          //         <div className="col-span-1 text-sm">{doc.loaderType}</div>
          //         <div className="col-span-3 text-sm">
          //           {doc.textSplitMethod}
          //         </div>

          //         <div className="col-span-2">
          //           <Badge variant="outline">{doc.chunkSize}</Badge>
          //         </div>

          //         <div className="col-span-2">
          //           <Badge variant="outline">{doc.chunkOverlap}</Badge>
          //         </div>

          //         {/* DELETE BUTTON HERE ✅ */}
          //         <div className="col-span-1 flex justify-center">
          //           <button
          //             className="text-red-500 hover:text-red-700"
          //             onClick={(e) => {
          //               e.stopPropagation(); // Prevent triggering row click
          //               deleteDoc(doc.id);
          //             }}
          //           >
          //             <Trash2 className="h-4 w-4" />
          //           </button>
          //         </div>
          //       </div>
          //     ))}
          //   </div>
          // </div>
        )}
      </main>

      {/* Dialogs */}
      <DocumentLoaderSelectionDialog
        open={showLoaderDialog}
        onOpenChange={async(open) => {
          if(!open){
            setSelectedDocument(null)
          }  
          handleLoaderOpenChange(open)
        }}
        datastoreId={datastore?.id}
        selectedDocument={selectedDocument}
      />

      <EmbeddingConfigWizard
        open={showEmbeddingWizard}
        onOpenChange={async(open) => {
          if(!open){
            await fetchDocuments(datastore.id);
          }  
          setShowEmbeddingWizard(open)
        }}
        datastoreId={datastore?.id}
        startingStep={datastore?.embeddingModel ? 3 : 1}
        shouldUpsert={shouldUpsert}
      />
    </div>
  );
};
