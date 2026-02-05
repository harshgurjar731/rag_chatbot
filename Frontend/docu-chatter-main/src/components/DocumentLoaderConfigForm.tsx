import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ArrowLeft, Upload, Eye, Database } from "lucide-react";
import { TextSplitterSelectionDialog } from "./TextSplitterSelectionDialog";
import { ChunkPreviewDialog } from "./ChunkPreviewDialog";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import axios from "axios";
import { DocumentObj } from "@/pages/DatastoreConfigDetail";
import CreateFolderDialog from "./CreateFolder";
import FolderBreadcrumbs from "./FolderBreadcrums";

interface DocumentLoaderConfigFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loaderType: string;
  datastoreId?: number;
  onBack: () => void;
  selectedDocument?: DocumentObj;
}

export const DocumentLoaderConfigForm = ({
  open,
  onOpenChange,
  loaderType,
  datastoreId,
  onBack,
  selectedDocument,
}: DocumentLoaderConfigFormProps) => {
  const { toast } = useToast();
  const [selectedFiles, setSelectedFiles] = useState<File[] | null>([]);
  const [selectedFileName, setSelectedFileName] = useState<string|null>(null);
  const [metadata, setMetadata] = useState("{}");
  const [omitKeys, setOmitKeys] = useState("key1, key2, key3.nestedKey1");
  const [selectedSplitter, setSelectedSplitter] = useState<string>("");
  const [splitterConfig, setSplitterConfig] = useState<any>(null);
  const [showSplitterDialog, setShowSplitterDialog] = useState(false);
  const [chunks, setChunks] = useState<any[]>([]);
  const [showChunkPreview, setShowChunkPreview] = useState(false);
  const [showCount, setShowCount] = useState(10);
  const [editMode, setEditMode] = useState<boolean>(false);
  const [currentFolder, setCurrentFolder] = useState(null);
  const [folders, setFolders] = useState([]);
  const [files, setFiles] = useState([]);
  const [breadcrumbs, setBreadcrumbs] = useState([]);

  const loaderNames: Record<string, string> = {
    docx: "Docx File",
    csv: "Csv File",
    file: "File Loader",
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFiles((p) => p ? [...p, ...Array.from(e.target.files)] : Array.from(e.target.files));
      setSelectedFileName(e.target.files[0].name)
      setChunks([])
      if (e.target.files[0]) {
        const reader = new FileReader();
        reader.readAsDataURL(e.target.files[0]);

        reader.onload = () => {
          console.log("Base64:", reader.result);
        };
      }
    }
  };
 
  async function loadFolderStructure(datastore_id: number, folderId = null) {

    const url = new URL(
      `http://127.0.0.1:8000/ingestion/datastore/${datastore_id}/folders`
    );

    if (folderId !== null && folderId !== undefined) {
      url.searchParams.append("parent_id", String(folderId));
    }

    const res = await fetch(url.toString());
    const data = await res.json();
    console.log("Folder Data", data);
    setFolders(data.folders);
    setFiles(data.files);
    setCurrentFolder(data.current_folder.id);
    // load breadcrumbs
    const breadcrumsRes = await fetch(
      `http://127.0.0.1:8000/ingestion/folders/${data.current_folder.id}/breadcrumbs`
    );
    const breadcrumData = await breadcrumsRes.json();
    setBreadcrumbs(breadcrumData);
  }

  useEffect(() => {
    if (selectedDocument) {
      setEditMode(true)
      setSelectedFileName(selectedDocument.filename)
      setSelectedSplitter(selectedDocument.textSplitMethod)
      const config = {
      chunkSize: selectedDocument.chunkSize,
      chunkOverlap: selectedDocument.chunkOverlap,
      customSeparators: "",
      }
      setSplitterConfig(config)
    }
  }, [selectedDocument])

  useEffect(() => {
    loadFolderStructure(datastoreId)
  }, [])

  useEffect(() => {
    if (!open) {
      setEditMode(false)
      setSelectedFileName(null)
      setSelectedSplitter("")
      setSplitterConfig(null)
      setChunks([])
      setShowChunkPreview(false)
      setMetadata("{}")
    }
  }, [open])

  const handleExistingFilePreviewChunks = async() => {
    const requestData = {
      datastoreId:selectedDocument.datastore_id,
      id: Number(selectedDocument.id)
    }
    const chunksResponse = await axios.post(`http://127.0.0.1:8000/ingestion/document/getChunks?previewLimit=${showCount}`, requestData);
    setChunks(chunksResponse.data.chunks)
  }

  const handleNewFilePreviewChunks = async() => {
    const formData = new FormData();
    formData.append("file", selectedFiles?.[0]);
    formData.append("documentDetails", JSON.stringify({ 
        filename: selectedFiles?.[0].name || "",
        loaderType: loaderType,
        textSplitMethod: selectedSplitter || "",
        chunkSize: splitterConfig?.chunkSize || 0,
        chunkOverlap: splitterConfig?.chunkOverlap || 0,
        folder_id: currentFolder,
    }));
    const chunksResponse = await axios.post(`http://127.0.0.1:8000/ingestion/document/previewChunks?previewLimit=${showCount}`, formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    console.log("Final Resp:", chunksResponse.data)
    setChunks(chunksResponse.data.chunks)
  };

  const handleProcess = async () => {
    toast({
      title: "Processing Document",
      description: "Your document is being processed and will be added to the datastore.",
    });

    const formData = new FormData();

    selectedFiles?.forEach((file, index) => {
      formData.append("files", file);

      // FastAPI expects documentDetails[i] to be a JSON string
      formData.append("documentDetails", JSON.stringify({ 
        filename: file.name || "",
        loaderType: loaderType,
        textSplitMethod: selectedSplitter || "",
        chunkSize: splitterConfig?.chunkSize || 0,
        chunkOverlap: splitterConfig?.chunkOverlap || 0,
        folder_id: currentFolder,
      }));
    });

    const response = await axios.post(`http://127.0.0.1:8000/ingestion/datastore/${datastoreId}/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" }
    });
    console.log("Starting processing after upload")
    const processResponse = await axios.post(`http://127.0.0.1:8000/ingestion/document/process`, response.data);
    console.log("Processed Docs ", processResponse.data)
    onOpenChange(false)
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <div className="flex items-center gap-3">
              {!selectedDocument && (
                <Button variant="ghost" size="icon" onClick={onBack}>
                  <ArrowLeft className="h-5 w-5" />
                </Button>
              )}
              <div className="flex items-center gap-3">
                <DialogTitle className="text-2xl">
                  {loaderNames[loaderType] || "Document Loader"}
                </DialogTitle>
                <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                  📄
                </div>
              </div>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto">
            <div className="grid grid-cols-2 gap-6">
              {/* Left Column - Configuration */}
              <div className="space-y-6">
                {/* File Upload */}
                <div className="space-y-2">
                  <Label htmlFor="file" className="text-base font-semibold">
                    {loaderNames[loaderType] || "File"}{" "}
                    <span className="text-destructive">*</span>
                  </Label>
                  {!editMode && (
                    <>
                      <p className="text-sm text-muted-foreground">
                        Choose a file to upload
                      </p>
                      <div className="border-2 border-dashed rounded-lg p-8 text-center hover:border-primary transition-colors cursor-pointer">
                        <input
                          id="file"
                          multiple
                          type="file"
                          accept=".pdf,.docx,.txt,.jpg,.jpeg,.png,.webp,.csv"
                          onChange={handleFileChange}
                          className="hidden"
                        />
                        <label htmlFor="file" className="cursor-pointer">
                          <Upload className="h-8 w-8 mx-auto mb-2 text-primary" />
                          <p className="text-sm font-medium">
                            {selectedFiles?.length > 0 ? "" : "Upload File"}
                          </p>
                        </label>
                      </div>
                      {selectedFiles.length > 0 && (
                        <ul className="text-xs text-muted-foreground italic mt-2">
                          {selectedFiles.map((file, index) => (
                            <li key={index}>{file.name}</li>
                          ))}
                        </ul>
                      )}
                       <div>
                        <p className="text-sm text-muted-foreground"> Selected Folder: </p>
                        <FolderBreadcrumbs
                          breadcrumbs={breadcrumbs}
                          onNavigate={(id) => loadFolderStructure(datastoreId, id)}
                        />
                        <div>
                          {folders.map(f => (
                            <div
                              key={f.id}
                              onClick={() => loadFolderStructure(datastoreId, f.id)}
                              className="pl-4 text-sm text-muted-foreground cursor-pointer hover:text-foreground"
                            >
                              📁 {f.name}
                            </div>
                          ))}
                        </div>
                        <CreateFolderDialog
                          currentFolderId={currentFolder}
                          onCreated={() => loadFolderStructure(datastoreId, currentFolder)}
                        />

                        <hr />
                      </div>
                    </>
                  )}
                  {/* {selectedFiles && (
                    selectedFiles.map((file, index) => (
                      <p key={index} className="text-xs text-muted-foreground italic">{file.name}</p>
                    ))
                  )} */}
                </div>

                {/* Additional Metadata */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Label
                      htmlFor="metadata"
                      className="text-base font-semibold"
                    >
                      Additional Metadata
                    </Label>
                    <div className="w-4 h-4 rounded-full bg-muted flex items-center justify-center text-xs">
                      ℹ️
                    </div>
                  </div>
                  <Textarea
                    id="metadata"
                    value={metadata}
                    onChange={(e) => setMetadata(e.target.value)}
                    placeholder='{ "key": "value" }'
                    className="font-mono text-sm"
                    rows={3}
                  />
                </div>

                {/* Omit Metadata Keys */}
                {/* <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Label htmlFor="omitKeys" className="text-base font-semibold">
                      Omit Metadata Keys
                    </Label>
                    <div className="w-4 h-4 rounded-full bg-muted flex items-center justify-center text-xs">
                      ℹ️
                    </div>
                  </div>
                  <Input
                    id="omitKeys"
                    value={omitKeys}
                    onChange={(e) => setOmitKeys(e.target.value)}
                    placeholder="key1, key2, key3.nestedKey1"
                    className="font-mono text-sm"
                  />
                </div> */}

                {/* Text Splitter */}
                <div className="space-y-4">
                  <div className="p-6 rounded-lg border bg-card">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold">Text Splitter</h3>
                      {/* <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                        ✂️
                      </div> */}
                    </div>
                    {selectedSplitter ? (
                      <div className="space-y-3">
                        {/* <div className="flex items-center justify-between p-3 rounded-lg bg-muted">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">Splitter</span>
                          </div>
                        </div> */}
                        <div className="p-3 rounded-lg bg-muted">
                          <p className="font-medium mb-2">{selectedSplitter}</p>
                          {splitterConfig && (
                            <div className="space-y-1 text-sm text-muted-foreground">
                              <p>Chunk Size: {splitterConfig.chunkSize}</p>
                              <p>
                                Chunk Overlap: {splitterConfig.chunkOverlap}
                              </p>
                            </div>
                          )}
                        </div>
                        <Button
                          variant="outline"
                          onClick={() => {
                            setShowSplitterDialog(true);
                            setChunks([]);
                          }}
                          className="w-full"
                        >
                          Change Splitter
                        </Button>
                      </div>
                    ) : (
                      <Button
                        onClick={() => setShowSplitterDialog(true)}
                        variant="outline"
                        className="w-full"
                      >
                        Select Splitter
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column - Preview */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">
                    {chunks.length > 0
                      ? `${chunks.length} of ${chunks.length} Chunks`
                      : "Preview"}
                  </h3>
                  <div className="flex items-center gap-2">
                    <Label htmlFor="showCount" className="text-sm">
                      Show Chunks in Preview
                    </Label>
                    <Input
                      id="showCount"
                      type="number"
                      value={showCount}
                      onChange={(e) => {
                        setShowCount(Number(e.target.value));
                        setChunks([]);
                      }}
                      className="w-20"
                    />
                  </div>
                </div>

                {chunks.length === 0 ? (
                  <div className="border-2 border-dashed rounded-lg p-12 text-center">
                    <Eye className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                    <Button
                      onClick={
                        editMode
                          ? handleExistingFilePreviewChunks
                          : handleNewFilePreviewChunks
                      }
                      variant="chatbot"
                      size="lg"
                      disabled={
                        (!selectedFiles ||
                          selectedFiles.length == 0 ||
                          !selectedSplitter) &&
                        !editMode
                      }
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      Preview Chunks
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[500px] overflow-y-auto">
                    {chunks.map((chunk, index) => (
                      <div
                        key={chunk.id}
                        className="p-4 rounded-lg border bg-card"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-semibold">
                            #{index + 1}. Characters: {chunk.length}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-3">
                          {chunk}
                        </p>
                      </div>
                    ))}
                    {/* <Button
                      onClick={() => setShowChunkPreview(true)}
                      variant="outline"
                      className="w-full"
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      Preview
                    </Button> */}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button
              variant="chatbot"
              onClick={handleProcess}
              disabled={
                !selectedFiles ||
                selectedFiles.length == 0 ||
                (loaderType == "pdf" &&
                  !selectedSplitter &&
                  chunks.length === 0)
              }
            >
              <Database className="h-4 w-4 mr-2" />
              Process
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <TextSplitterSelectionDialog
        open={showSplitterDialog}
        onOpenChange={setShowSplitterDialog}
        onSelect={(splitter, config) => {
          setSelectedSplitter(splitter);
          setSplitterConfig(config);
        }}
      />

      <ChunkPreviewDialog
        open={showChunkPreview}
        onOpenChange={setShowChunkPreview}
        chunks={chunks}
      />
    </>
  );
};
