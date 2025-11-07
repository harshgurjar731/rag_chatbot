import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TimelineStep } from "@/components/TimelineStep";
import { ArrowLeft, Eye } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { Outlet } from "react-router-dom";

const timelineSteps = [
  "Document Uploaded",
  "Document Chunked",
  "Indexing Completed",
  "Embedding Completed"
];

const EvaluationTimeline = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [isCompleted, setIsCompleted] = useState(false);
  const { id } = useParams<{ id: string }>();

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentStep(prev => {
        if (prev < timelineSteps.length - 1) {
          return prev + 1;
        } else {
          setIsCompleted(true);
          clearInterval(timer);
          return prev;
        }
      });
    }, 2000);

    return () => clearInterval(timer);
  }, []);

  const getStepStatus = (index: number) => {
    if (index < currentStep) return "completed";
    if (index === currentStep && !isCompleted) return "current";
    if (index === currentStep && isCompleted) return "completed";
    return "clickable";
  };

  return (
    <div className="min-h-screen bg-gradient-surface">
      <header className="border-b bg-card shadow-card">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center space-x-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/evaluation-selection")}
              className="hover:bg-muted"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Selection
            </Button>
            <div>
              <h1 className="text-2xl font-bold">Evaluation Process</h1>
              <p className="text-muted-foreground">Track the steps of document processing and evaluation</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid gap-6">
          <Card className="shadow-elegant">
            <CardHeader>
              <CardTitle>Processing Timeline</CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="flex items-start justify-center space-x-0 overflow-x-auto">
                {timelineSteps.map((step, index) => (
                  <TimelineStep
                    key={index}
                    label={step}
                    status={getStepStatus(index)}
                    isLast={index === timelineSteps.length - 1}
                  />
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="shadow-elegant">
            <CardContent className="pt-6">
              <Button
                onClick={() => navigate(`/rag-output/${id}`)}
                disabled={!isCompleted}
                className="w-full bg-gradient-primary hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                <Eye className="h-4 w-4 mr-2" />
                Show Result
              </Button>

            </CardContent>
          </Card>
        </div>
      </main>
      <Outlet />
    </div>
  );
};

export default EvaluationTimeline;
