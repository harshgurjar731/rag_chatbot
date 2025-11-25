import { AssistantCard } from "@/components/AssistantCard";
import { Outlet } from "react-router-dom";
import { ChatbotCard } from '@/components/ChatbotCard';
import { CreateChatbotDialog } from '@/components/CreateChatbotDialog';
import { useChatbots } from '@/hooks/useChatbots';
import { useNavigate } from 'react-router-dom';
// UI Components
import { Button } from "@/components/ui/button";

// Icons (from lucide-react)
import {
    Bot,
    ArrowLeft,
    BarChart3,
    Plus,
    FileSpreadsheet,
    Activity,
    ChartBar,
} from "lucide-react";

// Custom Components
// import { CreateEvaluationDialog } from "@/components/evaluation/CreateEvaluationDialog";
// import { EvaluationList } from "@/components/evaluation/EvaluationList";

const EvaluationDashboard = () => {

    const { chatbots } = useChatbots();
    const navigate = useNavigate();

    const handleChatbotClick = (id: string) => {
        navigate(`/evaluation-selection/${id}`);
    };
    return (
        <div className="min-h-screen bg-gradient-surface">
            <header className="border-b border-chatbot-primary/20 bg-gradient-card">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                    <div className="flex items-center gap-4">
                        <div className="p-3 rounded-lg bg-gradient-primary">
                            <Bot className="h-8 w-8 text-primary-foreground" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold bg-gradient-primary bg-clip-text text-transparent">
                                Knowledge Assistant Evaluation
                            </h1>
                        </div>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
  {chatbots.length === 0 ? (
    /* 🎯 Empty State: No Chatbots Found */
    <div className="flex flex-col items-center justify-center min-h-[70vh] text-center">
      <div className="p-8 rounded-full bg-gradient-to-br from-blue-500/10 to-indigo-500/10 mb-6 shadow-inner">
        <Bot className="h-16 w-16 text-blue-600" />
      </div>

      <h2 className="text-2xl sm:text-3xl font-semibold mb-3 text-foreground">
        No Chatbots Found
      </h2>

      <p className="text-muted-foreground mb-8 max-w-md text-sm sm:text-base leading-relaxed">
        You haven’t created any AI assistants yet.  
        To start evaluating performance, please create a chatbot from your dashboard.
      </p>

      <Button
        onClick={() => navigate('/')}
        variant="chatbot"
        size="lg"
        className="flex items-center gap-2 px-6 py-5 rounded-xl shadow-md hover:shadow-lg transition-all duration-200"
      >
        <ArrowLeft className="h-5 w-5" />
        Back to Dashboard
      </Button>
    </div>
  ) : (
    /* 💬 Chatbot Cards Grid */
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      {chatbots.map((chatbot) => (
        <AssistantCard
          key={chatbot.id}
          chatbot={chatbot}
          onClick={() => handleChatbotClick(chatbot.id)}
        />
      ))}
    </div>
  )}
</main>
            <Outlet />
        </div >
    )
};


export default EvaluationDashboard;
