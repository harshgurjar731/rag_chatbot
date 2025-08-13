import React from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
// import { MultiSelect } from "@/components/ui/multi-select";
import Select from "react-select";

interface ChatInputSelectionProps {
  documents: any[];
  selectedDocs: any[];
  setSelectedDocs: (docs: any[]) => void;
  optimizer: string;
  setOptimizer: (val: string) => void;
  embeddingModel: string;
  setEmbeddingModel: (val: string) => void;
  llmModel: string;
  setLlmModel: (val: string) => void;
  vectorDb: string;
  setVectorDb: (val: string) => void;
}

const ChatInputSelection: React.FC<ChatInputSelectionProps> = ({
  documents,
  selectedDocs,
  setSelectedDocs,
  optimizer,
  setOptimizer,
  embeddingModel,
  setEmbeddingModel,
  llmModel,
  setLlmModel,
  vectorDb,
  setVectorDb,
}) => {
  const documentOptions = documents.map((doc: any) => ({
    label: doc.filename,
    value: doc.id,
  }));

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mb-4">
      
      {/* Document Selector */}
      <div>
         <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Select Documents
        </label>
        <div className="space-y-2">
          {documentOptions.map((doc) => (
            <label key={doc.value} className="flex items-center space-x-2">
              <input
                type="checkbox"
                value={doc.value}
                checked={selectedDocs.includes(doc.value)}
                onChange={(e) => {
                  const newSelected = e.target.checked
                    ? [...selectedDocs, doc.value]
                    : selectedDocs.filter((d) => d !== doc.value);
                  setSelectedDocs(newSelected);
                }}
              />
              <span>{doc.label}</span>
            </label>
          ))}
        </div>
      </div>
      
      </div>

      {/* Query Optimizer */}
      <div>
        <Label>Query Optimizer</Label>
        <Input
          value={optimizer}
          onChange={(e) => setOptimizer(e.target.value)}
          placeholder="e.g., BM25, TF-IDF"
        />
      </div>

      {/* Embedding Model */}
      <div>
        <Label>Embedding Model</Label>
        <Input
          value={embeddingModel}
          onChange={(e) => setEmbeddingModel(e.target.value)}
          placeholder="e.g., all-MiniLM, bge-base"
        />
      </div>

      {/* LLM Model */}
      <div>
        <Label>LLM Model</Label>
        <Input
          value={llmModel}
          onChange={(e) => setLlmModel(e.target.value)}
          placeholder="e.g., gpt-4, llama3"
        />
      </div>

      {/* Vector DB */}
      <div>
        <Label>Vector DB</Label>
        <Input
          value={vectorDb}
          onChange={(e) => setVectorDb(e.target.value)}
          placeholder="e.g., FAISS, Pinecone"
        />
      </div>
    </div>
  );
};

export default ChatInputSelection;
