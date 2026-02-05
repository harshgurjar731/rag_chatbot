import { useState, useEffect } from 'react';
import { Chatbot, CreateChatbotDataResponse, QnAPair, RawDatastore, FileRecord, DocumentRecord, CreateDatastoreData } from '@/types/chatbot';
import axios from 'axios';
import { toast } from "@/components/ui/use-toast";
import { IdCard } from 'lucide-react';


const STORAGE_KEY = 'multi-chatbot-data';

// export interface Datastore {
//   id: string;
//   name: string;
//   description?: string; // Include other fields if present in your backend model
// }

// const [datastores, setDatastores] = useState<Datastore[]>([]);


// export const useChatbots = () => {
//   const [chatbots, setChatbots] = useState<Chatbot[]>([]);

//   useEffect(() => {
//     const stored = localStorage.getItem(STORAGE_KEY);
//     if (stored) {
//       try {
//         const parsed = JSON.parse(stored);
//         setChatbots(parsed.map((bot: any) => ({
//           ...bot,
//           createdAt: new Date(bot.createdAt),
//           updatedAt: new Date(bot.updatedAt),
//         })));
//       } catch (error) {
//         console.error('Failed to parse stored chatbots:', error);
//       }
//     }

//   //   useEffect(() => {
//   // const fetchDatastores = async () => {
//   //   try {
//   //     const response = await axios.get<Datastore[]>('http://127.0.0.1:8000/datastore/');
//   //     setDatastores(response.data);
//   //   } catch (err) {
//   //     console.error('Failed to fetch datastores:', err);
//   //   }
//   // };

//   // fetchDatastores();
// }, []);


export const useChatbots = () => {
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchChatbotsWithFiles = async () => {
    try {
      // Step 1: Get all assistants
      const res = await axios.get("http://127.0.0.1:8000/rag/getAssistants/");
      const assistants = res.data;

      const fetchedDatastores = JSON.parse(localStorage.getItem("createdDataStores")
            || "[]");
      console.log("Fetched List of Assistants", res.data)
      const list_chatbots: Chatbot[] = []
      // Step 2: Fetch files for each datastore
      const chatbotPromises = assistants.map(async (assistant) => {
        let files: DocumentRecord[] = [];
        try {
          const fileRes = await axios.get<DocumentRecord[]>(
            `http://127.0.0.1:8000/ingestion/datastore/${assistant.datastore_id}/documents`
          );
          files = fileRes.data;
         

        } catch (fileErr) {
          console.warn(`Failed to fetch files for datastore ${assistant.id}`, fileErr);
        }
        const fetchedDatastore = fetchedDatastores.find((ds: CreateDatastoreData) => ds.id === Number(assistant.datastore_id))
        console.log("Fetched Datastore: ", fetchedDatastore)
        return {
          id: assistant.id,
          name: assistant.name,
          description: assistant.description,
          documents: files.map((file) => file.filename),
          createdAt: new Date(assistant.created_at),
          datastoreId: assistant.datastore_id,
          datastoreName: fetchedDatastore.name
        };
      });

      const chatbotData = await Promise.all(chatbotPromises);
      setChatbots(chatbotData);
      setError(null);
    } catch (err: any) {
      console.error("Error fetching chatbots:", err);
      setError("Could not load chatbots and documents.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchChatbotsWithFiles();
  }, []);


  // const saveChatbots = (bots: Chatbot[]) => {
  //   localStorage.setItem(STORAGE_KEY, JSON.stringify(bots));
  //   setChatbots(bots);
  // };
  // const updateChatbotIdApiCall = async (datastoreId: number, chatbotId: string) => {
  //   const response = await axios.put(`http://127.0.0.1:8000/datastore/${datastoreId}`, null, {
  //     params: {
  //       chatbot_id: chatbotId,
  //     },
  //   });
  //   return response.data;
  // };

//   const createChatbot = (data: CreateChatbotData): Chatbot => {
//   const newBot: Chatbot = {
//     id: crypto.randomUUID(),
//     name: data.name,
//     topic: data.topic,
//     // ✅ Handle multiple documents
//     documents: data.documents
//       ? data.documents.map((file) => file.name)
//       : [],
//     qna: [],
//     createdAt: new Date(),
//     updatedAt: new Date(),
//     icon: getRandomIcon(),
//     datastoreId: data.id,
//   };

//   updateChatbotIdApiCall(newBot.datastoreId, newBot.id);

//   const updated = [...chatbots, newBot];
//   saveChatbots(updated);

//   return newBot;
// };


  const deleteChatbot = async(id: string) => {
    //To delete from DB.. Not handling local storage
    // const updated = chatbots.filter(bot => bot.id !== id);
    // saveChatbots(updated);
    try {
      const fileRes = await axios.post(`http://127.0.0.1:8000/rag/deleteAssistant/${id}`);
    } catch (error) {
        console.warn(`Error while deleting chatbot ${id}`, error);
    }
  };



  // const updateChatbot = (id: string, updates: Partial<Chatbot>) => {
  //   const updated = chatbots.map(bot =>
  //     bot.id === id
  //       ? { ...bot, ...updates, updatedAt: new Date() }
  //       : bot
  //   );
  //   saveChatbots(updated);
  // };
  // const uploadFileToDatastore = async (datastoreId: number, file: File) => {
  //   const formData = new FormData();
  //   formData.append("file", file);

  //   const response = await axios.post(
  //     `http://127.0.0.1:8000/datastores/${datastoreId}/upload`,
  //     formData,
  //     {
  //       headers: {
  //         "Content-Type": "multipart/form-data",
  //       },
  //     }
  //   );
  //   return response.data; // { message, file_id, filename }
  // };

  // const triggerChunking = async (
  //   datastoreId: number,
  //   fileId: number,
  //   method: string = "recursive",
  //   chunkSize: number = 512,
  //   chunkOverlap: number = 50
  // ): Promise<void> => {
  //   try {
  //     await axios.get(
  //       `http://172.200.163.232:8000/datastores/${datastoreId}/files/${fileId}/chunk`,
  //       {
  //         params: {
  //           method,
  //           chunk_size: chunkSize,
  //           chunk_overlap: chunkOverlap
  //         }
  //       }
  //     );

  //     // No need to handle response if you're not using the returned chunks
  //     console.log("Chunking triggered successfully.");
  //   } catch (error: any) {
  //     console.error("Error triggering chunking:", error);
  //     // You may also add toast/notification here if needed
  //   }
  // };
  // const triggerEmbedding = async (datastoreId: number, fileId: number) => {
  //   try {
  //     const response = await axios.post(
  //       `http://172.200.163.232:8000/embedding/store`,
  //       null, // No body in POST
  //       {
  //         params: {
  //           datastore_id: datastoreId,
  //           file_id: fileId,
  //           model_name: "all-MiniLM-L6-v2", // or allow dynamic model name
  //           vector_db: "faiss", // or dynamic
  //         },
  //       }
  //     );

  //     toast({
  //       title: "Embedding Success",
  //       description: "Document successfully embedded and stored in vector DB.",
  //     });

  //     return response.data;
  //   } catch (error: any) {
  //     console.error("Embedding error:", error);

  //     toast({
  //       title: "Embedding Failed",
  //       description:
  //         error?.response?.data?.detail || "An error occurred while storing embeddings.",
  //       variant: "destructive",
  //     });

  //     throw error;
  //   }
  // };
  // const addDocument = async (id: string, file: File) => {
  //   const bot = chatbots.find(b => b.id === id);
  //   if (bot) {
  //     const updatedDocuments = [...bot.documents, file.name];
  //     await uploadFileToDatastore(bot.datastoreId, file);
  //     // await new Promise((resolve) => setTimeout(resolve, 5000));

  //     // let fileId = null;
  //     // let loaderType="pdf"
  //     // try {
  //     //   const idRes = await axios.get<{ file_id: number }>(
  //     //     `http://172.200.163.232:8000/datastores/${bot.datastoreId}/files/${encodeURIComponent(file.name)}/id`
  //     //   );
  //     //   fileId = idRes.data.file_id;
  //     //   console.log(fileId)

  //     //   await triggerChunking(bot.datastoreId, fileId);
  //     // }
  //     // catch (error: any) {
  //     //   console.error("Error in file ID fetch or chunking:", error);

  //     //   toast({
  //     //     title: "Chunking Failed",
  //     //     description:
  //     //       error?.response?.data?.detail || "Something went wrong while preparing document chunks.",
  //     //     variant: "destructive",
  //     //   });
  //     // }
  //     // await new Promise((resolve) => setTimeout(resolve, 5000));
      
  //     // await triggerEmbedding(bot.datastoreId, fileId);

  //     updateChatbot(id, { documents: updatedDocuments });
  //   }
  // };

  // const addQnA = (id: string, qna: Omit<QnAPair, 'id'>) => {
  //   const bot = chatbots.find(b => b.id === id);
  //   if (bot) {
  //     const newQnA: QnAPair = {
  //       ...qna,
  //       id: crypto.randomUUID(),
  //     };
  //     const updatedQnA = [...bot.qna, newQnA];
  //     updateChatbot(id, { qna: updatedQnA });
  //   }
  // };

  const getChatbot = (id: string) => {
    return chatbots.find(bot => bot.id == id);
  };

  return {
    chatbots,
    // createChatbot,
    deleteChatbot,
    // updateChatbot,
    //addDocument,
    //addQnA,
    getChatbot,
    setChatbots,
    refetchChatbots: fetchChatbotsWithFiles,
    // triggerEmbedding,
    // triggerChunking,

  };
};