import { useEffect, useState } from 'react';
import { Plus, Bot, Sparkles, FileText, Database, DatabaseIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ChatbotCard } from '@/components/ChatbotCard';
import { CreateChatbotDialog } from '@/components/CreateChatbotDialog';
import { useChatbots } from '@/hooks/useChatbots';
import { useNavigate } from 'react-router-dom';

import axios from 'axios';
import { CreateDatastoreDialog } from '@/components/CreateDatastoreDialog';
import { CreateDatastoreData } from '@/types/chatbot';
import { set } from 'date-fns';
import { DatastoreCard } from '@/components/DatastoreCard';

export async function fetchDatastores(): Promise<CreateDatastoreData[]> {
      try {
        const response = await axios.get('http://127.0.0.1:8000/ingestion/getDatastores');
        var datastoresFromApi: CreateDatastoreData[] = [];
        response.data.forEach((ds: any) => {
          console.log("Datastore fetched:", ds);
          const dataStore = {
            id: ds.id, 
            name: ds.name, 
            description: ds.description, 
            updatedAt: ds.created_at,
            embeddingModel: ds.embedding_model,
            embeddingProvider: ds.embedding_provider,
            vectorStoreProvider: ds.vector_store_provider,
            similarityMetric: ds.similarity_metric,
            documentCount: ds.document_count
          }
          datastoresFromApi.push(dataStore);
        });
        localStorage.setItem("createdDataStores", JSON.stringify(datastoresFromApi || []));
        console.log("Datastores set:", datastoresFromApi);
        return datastoresFromApi || [];

      } catch (error) {
        console.error('Error fetching datastores:', error);
        localStorage.setItem("createdDataStores", JSON.stringify([]));
        return []; // Set to empty array on error
      }
  }

export const DatastoreDashboard = () => {
  const { chatbots, createChatbot } = useChatbots();
  const navigate = useNavigate();
  const [datastores, setDatastores] = useState<CreateDatastoreData[]>([]);

  const handleCreateDatastore = (data: any) => {
    //localStorage.setItem("createdDataStores", JSON.stringify([]));
    localStorage.setItem("createdDataStores", JSON.stringify([...datastores, data]));
    setDatastores((prev) => [...prev, data]);
  };

  

  useEffect(() => {
    const fetchStore = async() =>  {
      setDatastores(await fetchDatastores());
    }
    fetchStore()
  }, []);

  const handleDatastoreClick = (id: string) => {
    navigate(`/datastore/${id}`);
  };

  const refreshDashboard=async()=>{
    setDatastores(await fetchDatastores());
  };

  return (
    <div className="min-h-screen bg-gradient-surface">
      {/* Header */}
      <div className="border-b border-chatbot-primary/20 bg-gradient-card">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-lg bg-gradient-primary">
                <Database className="h-8 w-8 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-3xl font-bold text-foreground">Datastore Hub</h1>
                <p className="text-muted-foreground">Create and manage your Datastores</p>
              </div>
            </div>
            {datastores.length > 0 && <CreateDatastoreDialog onCreateDatastore={handleCreateDatastore}>
                <Button variant="chatbot" size="lg">
                  <Plus className="h-5 w-5" />
                  Create New Datastore
                </Button>
              </CreateDatastoreDialog>}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8">
        {datastores.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[500px] text-center">
            <div className="p-6 rounded-full bg-gradient-primary/10 mb-6">
              <DatabaseIcon className="h-16 w-16 text-chatbot-primary" />
            </div>
            <h2 className="text-2xl font-semibold mb-3 text-foreground">
              Welcome to Your Datastore Hub
            </h2>
            <p className="text-muted-foreground mb-8 max-w-md">
              Create datastore for different topics and documents. 
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 max-w-2xl">
              <div className="flex flex-col items-center p-4 rounded-lg bg-chatbot-surface-variant/50">
                <FileText className="h-8 w-8 text-chatbot-primary mb-2" />
                <h3 className="font-medium text-sm">Upload Documents</h3>
                <p className="text-xs text-muted-foreground text-center">
                   Upload PDFs, Word docs, and text files, images, etc.
                </p>
              </div>
              <div className="flex flex-col items-center p-4 rounded-lg bg-chatbot-surface-variant/50">
                <Bot className="h-8 w-8 text-chatbot-primary mb-2" />
                <h3 className="font-medium text-sm">Configure Store</h3>
                <p className="text-xs text-muted-foreground text-center">
                  Select processing details like embedding models, splitters, and more.
                </p>
              </div>
            </div>
            <CreateDatastoreDialog onCreateDatastore={handleCreateDatastore}>
            <Button variant="chatbot" size="lg">
              <Plus className="h-5 w-5" />
              Create New Datastore
            </Button>
            </CreateDatastoreDialog>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {datastores.map((store) => (
              <DatastoreCard
                data={store}
                onClick={() => handleDatastoreClick(String(store.id))}
                onDelete={refreshDashboard}
              />
            ))}
          </div>
        )}
      </div>

      {/* Floating Action Button for Mobile */}
      <CreateDatastoreDialog onCreateDatastore={handleCreateDatastore}>
        <Button
          variant="floating"
          size="floating"
          className="fixed bottom-6 right-6 md:hidden z-50"
        >
          <Plus className="h-6 w-6" />
        </Button>
      </CreateDatastoreDialog>
    </div>
  );
};

export default DatastoreDashboard;