import { Calendar, Database, FileText, MessageCircle, Trash, TrashIcon } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Chatbot } from '@/types/chatbot';
import { cn } from '@/lib/utils';
import { useEffect } from 'react';
import { useChatbots } from '@/hooks/useChatbots';

interface ChatbotCardProps {
  chatbot: Chatbot;
  onClick: () => void;
  onDelete: () => void;
  className?: string;
}

export const ChatbotCard = ({ chatbot, onClick, onDelete, className }: ChatbotCardProps) => {
  const { deleteChatbot } = useChatbots()
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
        "cursor-pointer group transition-all duration-300 hover:shadow-card-custom hover:scale-105 bg-gradient-card border-chatbot-primary/20 group",
        className
      )}
      onClick={onClick}
    >
      {/* ✅ DELETE ICON */}
      <div className='relative'>
      <button
        onClick={async(e) => {
          e.stopPropagation(); // prevent card click
          await deleteChatbot(chatbot.id);
          onDelete()
        }}
        className="absolute top-2 right-2 z-20 rounded-md opacity-0 group-hover:opacity-100
           transition-opacity duration-300 ease-in-out hover:bg-chatbot-primary/15 hover:scale-110"
      >
        <TrashIcon className="w-4 h-4 text-chatbot-primary" />
      </button>
      </div>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div>
              <CardTitle className="text-lg font-semibold text-foreground group-hover:text-chatbot-primary transition-colors">
                {chatbot.name}
              </CardTitle>
              <CardDescription className="text-muted-foreground mt-1">
                {chatbot.description}
              </CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <Database className="h-3 w-3" />
              <span>{chatbot.datastoreName}</span>
            </div>
            <div className="flex items-center gap-1">
              <FileText className="h-3 w-3" />
              <span>{chatbot.documents.length} docs</span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            <span>{formatDate(chatbot.createdAt)}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};