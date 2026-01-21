import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText, MessageSquare, Clock } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Chatbot } from '@/types/chatbot';


interface ChatbotCardProps {
  chatbot: Chatbot;
  onClick: () => void;
  className?: string;
}

export const AssistantCard = ({ chatbot, onClick, className }: ChatbotCardProps) => {
  const navigate = useNavigate();

  const handleCardClick = () => {
    navigate(`/evaluation-selection/${chatbot.id}`);
  };

  return (
    <Card
      className="group hover:shadow-elegant transition-all duration-300 hover:scale-[1.02] cursor-pointer"
      onClick={handleCardClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">{chatbot.name}</CardTitle>
          <Badge variant="default" className="bg-success text-success-foreground">
            Active
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center space-x-2">
            <FileText className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              {chatbot.documents.length} documents
            </span>
          </div>
          {/* <div className="flex items-center space-x-2">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              {chatbot.qna.length} Q&A
            </span>
          </div> */}
        </div>

        <div className="flex items-center space-x-2 text-sm text-muted-foreground">
          <Clock className="h-4 w-4" />
          <span>Created {chatbot.createdAt.toLocaleDateString()}</span>
        </div>
      </CardContent>
    </Card>
  );
};
