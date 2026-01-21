import { useEffect, useState } from 'react';
import { Plus, Bot, Sparkles, FileText, DatabaseIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ChatbotCard } from '@/components/ChatbotCard';
import { CreateChatbotDialog } from '@/components/CreateChatbotDialog';
import { useChatbots } from '@/hooks/useChatbots';
import { useNavigate } from 'react-router-dom';

import axios from 'axios';


export const Dashboard = () => {
  const { chatbots, createChatbot, refetchChatbots } = useChatbots();
  const navigate = useNavigate();

  const handleCreateChatbot = (data: any) => {
    refetchChatbots()
  };

  const handleChatbotClick = (id: string) => {
    navigate(`/chatbot/${id}`);
  };

  const refreshDashboard=async()=>{
      setDatastores(await fetchDatastores());
    };
  
  
  useEffect(()=> {
    console.log("Chatbots in Dashboard", chatbots)
  }, [chatbots])

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
            
            {chatbots.length !== 0 && (<CreateChatbotDialog onCreateChatbot={handleCreateChatbot}>
              <Button variant="chatbot" size="lg" className="hidden md:flex">
                <Plus className="h-5 w-5" />
                Create Assistant
              </Button>
            </CreateChatbotDialog>)}
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
              Welcome to your Knowledge Assistant Hub
            </h2>
            <p className="text-muted-foreground mb-8 max-w-md">
              Build and manage specialized AI assistants that use your organization’s knowledge to answer questions, automate workflows, and support your teams.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 max-w-2xl">
              <div className="flex flex-col items-center p-4 rounded-lg bg-chatbot-surface-variant/50">
                <DatabaseIcon className="h-8 w-8 text-chatbot-primary mb-2" />
                <h3 className="font-medium text-sm">Select datastore</h3>
                <p className="text-xs text-muted-foreground text-center">
                  Connect a datastore so your assistant retrieves answers from the right documents and respond using accurate, domain‑specific knowledge.
                </p>
              </div>
              <div className="flex flex-col items-center p-4 rounded-lg bg-chatbot-surface-variant/50">
                <Bot className="h-8 w-8 text-chatbot-primary mb-2" />
                <h3 className="font-medium text-sm">AI‑powered responses</h3>
                <p className="text-xs text-muted-foreground text-center">
                 Let assistants generate accurate, conversational answers grounded in your business knowledge, not generic internet data.
                </p>
              </div>
              <div className="flex flex-col items-center p-4 rounded-lg bg-chatbot-surface-variant/50">
                <Sparkles className="h-8 w-8 text-chatbot-primary mb-2" />
                <h3 className="font-medium text-sm">Voice & chat experience</h3>
                <p className="text-xs text-muted-foreground text-center">
                  Ask questions by text, image or voice and get instant, natural responses for faster decision‑making and support.
                </p>
              </div>
            </div>

            <CreateChatbotDialog onCreateChatbot={handleCreateChatbot}>
              <Button variant="chatbot" size="lg">
                <Plus className="h-5 w-5" />
                Create your first assistant
              </Button>
            </CreateChatbotDialog>
          </div>
        ) : (
          /* Chatbots Grid */
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-semibold text-foreground">Your knowledge assistants</h2>
                {/* <p className="text-muted-foreground">
                  {chatbots.length} assistant{chatbots.length !== 1 ? 's' : ''} ready to help
                </p> */}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {chatbots.map((chatbot) => (
                <ChatbotCard
                  key={chatbot.id}
                  chatbot={chatbot}
                  onClick={() => handleChatbotClick(chatbot.id)}
                  onDelete={refetchChatbots}
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