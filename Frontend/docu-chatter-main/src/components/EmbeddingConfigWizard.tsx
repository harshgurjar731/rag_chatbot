import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ArrowLeft, RefreshCw, Save, Search, Upload } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Switch } from "./ui/switch";
import axios from "axios";
import { fetchDatastores } from "@/pages/DatastoreDashboard";
import { CreateDatastoreData } from "@/types/chatbot";

interface EmbeddingConfigWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  datastoreId?: number;
  startingStep?: number;
  shouldUpsert?: boolean;
}

export const EmbeddingConfigWizard = ({
  open,
  onOpenChange,
  datastoreId,
  startingStep,
  shouldUpsert
}: EmbeddingConfigWizardProps) => {
  const [step, setStep] = useState(startingStep ?? 1);
  const [embeddingProvider, setEmbeddingProvider] = useState("HuggingFace");
  const [embeddingModel, setEmbeddingModel] = useState("all-MiniLM-L6-v2");
  const [similarityMetric, setSimilarityMetric] = useState("Cosine");
  const [vectorStore, setVectorStore] = useState("QDrant");
  const [retrievalQuery, setRetrievalQuery] = useState("");
  const [retrievalResultCount, setRetrievalResultCount] = useState(5);
  const [rerankEnabled, setRerankEnabled] = useState(true);
  const [loading, setLoading] = useState(false)
  const [datastore, setDatastore] = useState<CreateDatastoreData|null>(null)
  const [upsertPending, setUpsertPending] = useState(shouldUpsert)

  const steps = [
    { number: 1, label: "Embeddings", active: step >= 1 },
    { number: 2, label: "Vector Store", active: step >= 2 },
    { number: 3, label: "Test Retriever", active: step >= 3 },
  ];

  const embeddingProviders = {
    "HuggingFace": ["all-MiniLM-L6-v2", "bge-large-en", "e5-large-v2"],
    "OpenAI": ["text-embedding-3-small", "text-embedding-3-large"],
  };

  const similarityMetricOptions = ["Cosine", "Dot", "Euclidean"];

  const vectorStoreProviders = ["QDrant", "Pinecone", "Chroma"];

  const upsertDocuments = async() => {
    const upsertRequest = {
      embedding_provider: embeddingProvider,
      embedding_model: embeddingModel,
      similarity_metric: similarityMetric,
      vector_store_provider: vectorStore,
      normalize_embedding: false 
    }
    try {
      setLoading(true)
      const upsertResponse = await axios.post(`http://127.0.0.1:8000/ingestion/datastore/${datastoreId}/upsertDocs`, upsertRequest);
      console.log(upsertResponse)
      if (step <=2) {
        setStep(step + 1)
      };
      fetchDatastores();
      setUpsertPending(false)
      setLoading(false)
    } catch {
      console.log("Error calling Upsert Operation");
    }
    
  }

  const testRetriever = async() => {
    const retrieverRequest = {
      query_str: retrievalQuery,
      top_k: retrievalResultCount,
      rerank_enabled: rerankEnabled,
      embedding_provider: embeddingProvider,
      embedding_model: embeddingModel,
      similarity_metric: similarityMetric,
      vector_store_provider: vectorStore,
    }

    try {
      setLoading(true)
      const testRetreiverResponse = await axios.post(`http://127.0.0.1:8000/ingestion/datastore/${datastoreId}/testRetrieval`, retrieverRequest);
      console.log("Test Resp:", testRetreiverResponse)
      setLoading(false)
    } catch {
      console.log("Error calling Upsert Operation");
    }    
  }

  useEffect(()=> {
      console.log("In useEffect - EmbeddingWizard")
      const fetchedDatastores = JSON.parse(localStorage.getItem("createdDataStores")
            || "[]");
      
      const fetchedDatastore = fetchedDatastores.find((ds: CreateDatastoreData) => ds.id === datastoreId)
      console.log("In useEffect - fetchedDatastores Count", fetchedDatastore)
      setDatastore(fetchedDatastore)
      if(fetchedDatastore && fetchedDatastore.embeddingModel && fetchedDatastore.vectorStoreProvider) {
        setStep(startingStep)
        console.log("In useEffect - EmbeddingWizard in if")
        setEmbeddingModel(fetchedDatastore.embeddingModel)
        setEmbeddingProvider(fetchedDatastore.embeddingProvider)
        setVectorStore(fetchedDatastore.vectorStoreProvider)
        setSimilarityMetric(fetchedDatastore.similarityMetric)
      } else {
        setStep(1)
      }
      console.log("ShortUpsert", shouldUpsert)
      console.log("UpsertPending", upsertPending)
  }, [open])

  useEffect(() => {
    setUpsertPending(shouldUpsert)
  }, [shouldUpsert])

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
    } else {
      onOpenChange(false);
    }
  };

  const handleNext = () => {
    if (step < 3) {
      setStep(step + 1);
    }
  };

  const getStepColor = (stepNum: number) => {
    if (step === stepNum) {
      if (step != 3 && upsertPending) {
        
      }else if (step == 3 && upsertPending) {
        return "from-yellow-300 via-yellow-400 to-green-400";
      }
      return "from-pink-400 via-purple-500 to-blue-500";
    }
    if (step > stepNum) return "from-blue-400 via-blue-500 to-teal-500";
    return "from-yellow-300 via-yellow-400 to-green-400";
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={handleBack} className="rounded-full">
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div>
              <DialogTitle className="text-2xl">Oak & Barrel</DialogTitle>
              <p className="text-sm text-muted-foreground">Configure Embeddings, Vector Store and Record Manager</p>
            </div>
          </div>
        </DialogHeader>

        {/* Progress Steps */}
        <div className="flex items-center justify-center gap-16 py-6">
          {steps.map((s, idx) => (
            <div key={s.number} className="flex flex-col items-center relative">
              {idx > 0 && (
                <div className={`absolute right-full w-16 h-0.5 top-6 ${s.active ? 'bg-primary' : 'bg-muted'}`} />
              )}
              <div
                className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-bold mb-2 ${
                  step === s.number ? 'bg-primary' : step > s.number ? 'bg-primary/70' : 'bg-muted'
                }`}
              >
                {step > s.number ? '✓' : s.number}
              </div>
              <span className="text-sm font-medium">{s.label}</span>
            </div>
          ))}
        </div>

        {/* Step Content */}
        <div className="flex-1 overflow-y-auto">
          <div className="grid grid-cols-3 gap-6">
            {/* Step 1: Embeddings */}
            <Card className={`p-6 bg-gradient-to-br ${getStepColor(1)} ${step !== 1 && 'opacity-50'}`}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">
                  {step >= 1 ? 'Selected Embeddings' : 'Select Embedding'}
                </h3>
                <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                  📊
                </div>
              </div>
              {step >= 1 && (
                <div className="space-y-4">
                  <div>
                    <Label className="text-white">Embedding Provider <span className="text-red-300">*</span></Label>
                    <Select value={embeddingProvider} onValueChange={setEmbeddingProvider}>
                      <SelectTrigger className="bg-white/10 border-white/20 text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.keys(embeddingProviders).map((key) => (
                          <SelectItem value={key}>{key}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-white">Model Name <span className="text-red-300">*</span></Label>
                    <Select value={embeddingModel} onValueChange={setEmbeddingModel}>
                      <SelectTrigger className="bg-white/10 border-white/20 text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {embeddingProviders[embeddingProvider].map((item, idx) => (
                          <SelectItem key={item} value={item}>{item}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-white">Similarity Metric<span className="text-red-300">*</span></Label>
                    <Select value={similarityMetric} onValueChange={setSimilarityMetric}>
                      <SelectTrigger className="bg-white/10 border-white/20 text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {similarityMetricOptions.map((item, idx) => (
                          <SelectItem key={item} value={item}>{item}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </Card>

            {/* Step 2: Vector Store */}
            <Card className={`p-6 bg-gradient-to-br ${getStepColor(2)} ${step !== 2 && 'opacity-50'}`}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">
                  {step >= 2 ? 'Select Vector Store' : 'Selected Vector Store'}
                </h3>
                <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                  🗄️
                </div>
              </div>
              {step >= 2 && (
                <div className="space-y-4">
                  <div>
                    <Label className="text-white">Vector Store <span className="text-red-300">*</span></Label>
                    <Select value={vectorStore} onValueChange={setVectorStore}>
                      <SelectTrigger className="bg-white/10 border-white/20 text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {vectorStoreProviders.map((item, idx) => (
                          <SelectItem key={item} value={item}>{item}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}
            </Card>

            {/* Step 3: Record Manager */}
            <Card className={`p-6 bg-gradient-to-br ${getStepColor(3)} ${(step !== 3 || upsertPending) && 'opacity-50'}`}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">
                  {'Test Retrieval'}
                </h3>
                <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                  📋
                </div>
              </div>
              {step >= 3 && (
                <div className="space-y-4">
                  <div>
                    <Label className="text-white">Query<span className="text-red-300">*</span></Label>
                    <Input 
                      value={retrievalQuery}
                      onChange={(e) => setRetrievalQuery(e.target.value)}
                      className="bg-white/10 border-white/20 text-white placeholder:text-white/50"
                      placeholder="my-index"
                    />
                  </div>
                  <div>
                    <Label className="text-white">Top-K<span className="text-red-300">*</span></Label>
                    <Input 
                      value={retrievalResultCount}
                      onChange={(e) => setRetrievalResultCount(Number(e.target.value))}
                      className="bg-white/10 border-white/20 text-white placeholder:text-white/50"
                      placeholder="my-index"
                    />
                  </div>
                  <div className="flex items-center justify-between ">
                    <Label htmlFor="rerank-toggle" className="text-white">
                      Reranker<span className="text-red-300">*</span>
                    </Label>

                    <Switch
                      id="rerank-toggle"
                      checked={rerankEnabled}
                      onCheckedChange={setRerankEnabled}
                    />
                  </div>
                </div>
              )}
            </Card>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-between gap-3 pt-4 border-t">
          <Button variant="link" onClick={() => setStep(1)}>
          </Button>
          <div className="flex gap-3">
            {step < 3 && <Button variant="outline" onClick={handleBack}>
              Back
            </Button>}
            {step < 2 ? (
              <Button variant="chatbot-secondary" onClick={handleNext}>
                Next
              </Button>
            ) : (
              <>
                <Button 
                  variant="chatbot" 
                  onClick={()=> {
                    (step == 2 || upsertPending) ? upsertDocuments() : testRetriever()
                  }}
                  disabled = {(step == 3 && !upsertPending && retrievalQuery == "") || loading}
                  >
                  {(step == 2 || upsertPending) ? <Upload className="h-4 w-4 mr-2" /> : <Search className="h-4 w-4 mr-2" />}
                  
                  {(step == 2 || upsertPending) ? 'Upsert' : 'Test Retriever'}
                </Button>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
