import { AssistantCard } from "@/components/AssistantCard";
import { Bot } from "lucide-react";
import { Outlet } from "react-router-dom";
import { ChatbotCard } from '@/components/ChatbotCard';
import { CreateChatbotDialog } from '@/components/CreateChatbotDialog';
import { useChatbots } from '@/hooks/useChatbots';
import { useNavigate } from 'react-router-dom';

const EvaluationDashboard = () => {

    const { chatbots } = useChatbots();
    const navigate = useNavigate();

    const handleChatbotClick = (id: string) => {
        navigate(`/evaluation-selection/${id}`);
    };
    return (
      <div className="min-h-screen bg-gradient-surface">
        <div className="border-b border-chatbot-primary/20 bg-gradient-card">
          <div className="container mx-auto px-4 py-6">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-lg bg-gradient-primary">
                <Bot className="h-8 w-8 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-foreground">
                  Knowledge Assistant Evaluation
                </h1>
              </div>
            </div>
          </div>
        </div>
        <main className="max-w-7xl mx-auto py-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* {chatbots.map((chatbot) => (
                <ChatbotCard
                  key={chatbot.id}
                  chatbot={chatbot}
                  onClick={() => handleChatbotClick(chatbot.id)}
                />
              ))} */}
            {chatbots.map((chatbot) => (
              <AssistantCard
                key={chatbot.id}
                chatbot={chatbot}
                onClick={() => handleChatbotClick(chatbot.id)}
              />
            ))}
            {/* </div> */}
          </div>
        </main>
        <Outlet />
      </div>
    );
};

export default EvaluationDashboard;
