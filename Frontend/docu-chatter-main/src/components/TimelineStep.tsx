import { CheckCircle, Circle, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

interface TimelineStepProps {
  label: string;
  status: "completed" | "current" | "pending" | "clickable";
  isLast?: boolean;
  onClick?: () => void;
}

export const TimelineStep = ({ label, status, isLast = false, onClick }: TimelineStepProps) => {
  const isClickable = status === "clickable" || status === "completed";
  
  return (
    <div className="flex flex-col items-center space-y-3">
      <div className="flex items-center">
        <div 
          className={cn(
            "flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all duration-300",
            status === "completed" && "bg-success border-success text-success-foreground",
            status === "current" && "bg-primary border-primary text-primary-foreground animate-pulse",
            status === "pending" && "bg-muted border-border",
            status === "clickable" && "bg-primary border-primary text-primary-foreground hover:scale-110 cursor-pointer",
            isClickable && "hover:shadow-elegant"
          )}
          onClick={isClickable ? onClick : undefined}
        >
          {status === "completed" ? (
            <CheckCircle className="w-5 h-5" />
          ) : status === "current" ? (
            <Clock className="w-5 h-5" />
          ) : (
            <Circle className="w-5 h-5" />
          )}
        </div>
        {!isLast && (
          <div 
            className={cn(
              "h-0.5 w-16 ml-4 transition-colors duration-300",
              status === "completed" ? "bg-success" : "bg-border"
            )}
          />
        )}
      </div>
      <div className="text-center max-w-24">
        <h3 
          className={cn(
            "text-xs font-medium transition-colors duration-300 leading-tight",
            status === "completed" && "text-success",
            status === "current" && "text-primary",
            status === "pending" && "text-muted-foreground",
            status === "clickable" && "text-primary hover:text-primary-glow cursor-pointer"
          )}
          onClick={isClickable ? onClick : undefined}
        >
          {label}
        </h3>
      </div>
    </div>
  );
};
