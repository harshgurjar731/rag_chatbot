export interface QnAPair {
  id: string;
  question: string;
  answer: string;
}

// export interface ChatMessage {
//   id: string;
//   content: string;
//   isUser: boolean;
//   timestamp: Date;
// }
export interface ChatMessage {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;         // ✅ use Date instead of number
  originalContent?: string; // ✅ optional for storing un-translated text
};


export interface Chatbot {
  id: string;
  name: string;
  topic: string;
  documents: string[];
  qna: QnAPair[];
  createdAt: Date;
  updatedAt: Date;
  icon?: string;
  datastoreId:number;
}

export interface CreateChatbotData {
  id:number,
  name: string;
  topic: string;
  document?: File;
}


export interface RawDatastore {
  id: number;
  name: string;
  description: string;
  created_at: string;
  updated_at?: string;
  chatbotId: string;

  // Optional extended chatbot info
  topic?: string;
  documents?: string[];
  qna?: QnAPair[];
  icon?: string;
}

export interface FileRecord {
  id: number;
  filename: string;
  content_type: string;
  size: number;
  datastore_id: number;
  uploaded_at: string;
}