import { useState } from 'react';
import { Plus, Bot, Sparkles, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ChatbotCard } from '@/components/ChatbotCard';
import { CreateChatbotDialog } from '@/components/CreateChatbotDialog';
import { useChatbots } from '@/hooks/useChatbots';
import { useNavigate } from 'react-router-dom';

import axios from 'axios';


export const Dashboard = () => {
  const { chatbots, createChatbot } = useChatbots();
  const navigate = useNavigate();

  const handleCreateChatbot = (data: any) => {
    const newBot = createChatbot(data);
    navigate(`/chatbot/${newBot.id}`);
  };

  const handleChatbotClick = (id: string) => {
    navigate(`/chatbot/${id}`);
  };

  return (
    <div className="min-h-screen bg-gradient-surface">
      {/* Header */}
      <div className="border-b border-chatbot-primary/20 bg-gradient-card">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-lg bg-gradient-primary">
                <Bot className="h-8 w-8 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-foreground">Knowledge Assistant Hub</h1>
                <p className="text-muted-foreground">Create and manage your AI assistants</p>
              </div>
            </div>
            
            <CreateChatbotDialog onCreateChatbot={handleCreateChatbot}>
              <Button variant="chatbot" size="lg" className="hidden md:flex">
                <Plus className="h-5 w-5" />
                Create Assistant
              </Button>
            </CreateChatbotDialog>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8">
        {chatbots.length === 0 ? (
          /* Empty State */
          <div className="flex flex-col items-center justify-center min-h-[500px] text-center">
            <div className="p-6 rounded-full bg-gradient-primary/10 mb-6">
              <Bot className="h-16 w-16 text-chatbot-primary" />
            </div>
            <h2 className="text-2xl font-semibold mb-3 text-foreground">
              Welcome to Your AI Assistant Hub
            </h2>
            <p className="text-muted-foreground mb-8 max-w-md">
              Create specialized chatbots for different topics and documents. 
              Start by building your first AI assistant.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 max-w-2xl">
              <div className="flex flex-col items-center p-4 rounded-lg bg-chatbot-surface-variant/50">
                <FileText className="h-8 w-8 text-chatbot-primary mb-2" />
                <h3 className="font-medium text-sm">Upload Documents</h3>
                <p className="text-xs text-muted-foreground text-center">
                  Train your chatbot with PDFs, Word docs, and text files
                </p>
              </div>
              <div className="flex flex-col items-center p-4 rounded-lg bg-chatbot-surface-variant/50">
                <Bot className="h-8 w-8 text-chatbot-primary mb-2" />
                <h3 className="font-medium text-sm">AI-Powered Responses</h3>
                <p className="text-xs text-muted-foreground text-center">
                  Get intelligent answers based on your specific content
                </p>
              </div>
              <div className="flex flex-col items-center p-4 rounded-lg bg-chatbot-surface-variant/50">
                <Sparkles className="h-8 w-8 text-chatbot-primary mb-2" />
                <h3 className="font-medium text-sm">Voice Features</h3>
                <p className="text-xs text-muted-foreground text-center">
                  Speak your questions and hear responses read aloud
                </p>
              </div>
            </div>

            <CreateChatbotDialog onCreateChatbot={handleCreateChatbot}>
              <Button variant="chatbot" size="lg">
                <Plus className="h-5 w-5" />
                Create Your First Assistant
              </Button>
            </CreateChatbotDialog>
          </div>
        ) : (
          /* Chatbots Grid */
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-semibold text-foreground">Your Assistants</h2>
                <p className="text-muted-foreground">
                  {chatbots.length} assistant{chatbots.length !== 1 ? 's' : ''} ready to help
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {chatbots.map((chatbot) => (
                <ChatbotCard
                  key={chatbot.id}
                  chatbot={chatbot}
                  onClick={() => handleChatbotClick(chatbot.id)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Floating Action Button for Mobile */}
      <CreateChatbotDialog onCreateChatbot={handleCreateChatbot}>
        <Button
          variant="floating"
          size="floating"
          className="fixed bottom-6 right-6 md:hidden z-50"
        >
          <Plus className="h-6 w-6" />
        </Button>
      </CreateChatbotDialog>
    </div>
  );
};

export default Dashboard;