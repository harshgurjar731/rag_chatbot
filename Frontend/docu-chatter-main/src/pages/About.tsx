import { Bot, Database, Search, Brain, FileText } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export default function About() {
  return (
    <div className="min-h-screen bg-gradient-surface">
      {/* Header */}
      <div className="border-b border-chatbot-primary/20 bg-gradient-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-primary">
              <Bot className="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-foreground">
                Knowledge Synthesis
              </h1>
              <p className="text-sm text-muted-foreground">
                How your documents power accurate AI responses
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container mx-auto px-4 py-6 space-y-4">
        {/* What is RAG */}
        <Card className="bg-gradient-card border-chatbot-primary/20">
          <CardContent className="p-4 space-y-2">
            <h2 className="text-lg font-medium text-foreground">
              What is RAG?
            </h2>
            <p className="text-sm text-muted-foreground leading-snug">
              Retrieval-Augmented Generation (RAG) enhances large language models
              by combining them with external, searchable knowledge sources.
              Instead of relying only on training data, relevant documents are
              retrieved at query time and used as grounded context.
            </p>
            <p className="text-sm text-muted-foreground leading-snug">
              This enables accurate, explainable, and continuously up-to-date
              responses without retraining the model.
            </p>
          </CardContent>
        </Card>

        {/* Pipeline */}
        <Card className="bg-gradient-card border-chatbot-primary/20">
          <CardContent className="p-4 space-y-3">
            <h2 className="text-lg font-medium text-foreground">
              RAG Pipeline Components
            </h2>

            <div className="grid grid-cols-2 gap-3">
              <PipelineItem
                icon={<FileText />}
                title="Ingestion"
                text="Documents are parsed, cleaned, normalized, and split into meaningful chunks."
              />
              <PipelineItem
                icon={<Brain />}
                title="Embeddings"
                text="Text chunks are converted into vectors that capture semantic meaning."
              />
              <PipelineItem
                icon={<Database />}
                title="Vector Store"
                text="Embeddings are indexed for fast similarity search at scale."
              />
              <PipelineItem
                icon={<Search />}
                title="Retrieval"
                text="Top-k relevant chunks are selected based on query similarity."
              />
              <PipelineItem
                icon={<Bot />}
                title="Generation"
                text="The LLM generates responses grounded strictly in retrieved context."
                full
              />
            </div>
          </CardContent>
        </Card>

        {/* RAG vs Traditional */}
        <div className="grid grid-cols-3 gap-4">
        <Card className="bg-gradient-card border-chatbot-primary/20">
          <CardContent className="p-4 space-y-2">
            <h2 className="text-lg font-medium text-foreground">
              RAG vs Traditional LLMs
            </h2>

            <div className="grid grid-cols-2 gap-3 text-sm text-muted-foreground">
              <div>
                <p className="font-medium text-foreground">
                  Traditional LLM
                </p>
                <ul className="text-xs space-y-1">
                  <li>• Knowledge limited to training</li>
                  <li>• Becomes outdated</li>
                  <li>• Higher hallucination risk</li>
                </ul>
              </div>

              <div>
                <p className="font-medium text-foreground">
                  RAG-based System
                </p>
                <ul className="text-xs space-y-1">
                  <li>• Uses live document retrieval</li>
                  <li>• Always up-to-date</li>
                  <li>• Grounded, auditable answers</li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Benefits + When to Use */}
        
          <Card className="bg-gradient-card border-chatbot-primary/20">
            <CardContent className="p-4 space-y-2">
              <h2 className="text-lg font-medium text-foreground">
                Benefits
              </h2>
              <ul className="text-sm text-muted-foreground space-y-1">
                <li>• Reduced hallucinations</li>
                <li>• Grounded in source documents</li>
                <li>• No model retraining needed</li>
                <li>• Supports private enterprise data</li>
                <li>• Improves trust and explainability</li>
              </ul>
            </CardContent>
          </Card>

          <Card className="bg-gradient-card border-chatbot-primary/20">
            <CardContent className="p-4 space-y-2">
              <h2 className="text-lg font-medium text-foreground">
                When to Use RAG
              </h2>
              <p className="text-sm text-muted-foreground leading-snug">
                RAG is ideal for knowledge-intensive use cases where accuracy,
                traceability, and evolving data are critical.
              </p>
              <p className="text-xs text-muted-foreground leading-snug">
                Common applications include internal knowledge bases, policy
                search, research assistants, customer support, and compliance
                workflows.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function PipelineItem({
  icon,
  title,
  text,
  full = false,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
  full?: boolean;
}) {
  return (
    <div className={`flex gap-3 ${full ? "col-span-2" : ""}`}>
      <div className="text-chatbot-primary mt-0.5">
        {icon}
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">
          {title}
        </p>
        <p className="text-xs text-muted-foreground leading-snug">
          {text}
        </p>
      </div>
    </div>
  );
}
