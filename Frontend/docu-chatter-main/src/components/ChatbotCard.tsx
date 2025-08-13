import { Calendar, FileText, MessageCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Chatbot } from '@/types/chatbot';
import { cn } from '@/lib/utils';

interface ChatbotCardProps {
  chatbot: Chatbot;
  onClick: () => void;
  className?: string;
}

export const ChatbotCard = ({ chatbot, onClick, className }: ChatbotCardProps) => {
  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(date);
  };

  return (
    <Card 
      className={cn(
        "cursor-pointer transition-all duration-300 hover:shadow-card-custom hover:scale-105 bg-gradient-card border-chatbot-primary/20 group",
        className
      )}
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="text-2xl">{chatbot.icon}</div>
            <div>
              <CardTitle className="text-lg font-semibold text-foreground group-hover:text-chatbot-primary transition-colors">
                {chatbot.name}
              </CardTitle>
              <CardDescription className="text-muted-foreground mt-1">
                {chatbot.topic}
              </CardDescription>
            </div>
          </div>
          <Badge variant="secondary" className="text-xs">
            Active
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <FileText className="h-3 w-3" />
              <span>{chatbot.documents.length} docs</span>
            </div>
            <div className="flex items-center gap-1">
              <MessageCircle className="h-3 w-3" />
              <span>{chatbot.qna.length} Q&As</span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            <span>{formatDate(chatbot.updatedAt)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};