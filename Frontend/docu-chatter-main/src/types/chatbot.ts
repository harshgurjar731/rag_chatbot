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
// export interface ChatMessage {
//   id: string;
//   content: string;
//   isUser: boolean;
//   timestamp: Date;         // ✅ use Date instead of number
//   originalContent?: string; // ✅ optional for storing un-translated text
// };

export interface Citation {
  source: string; // Corresponds to the 'source' key in the Python dict
  pages: (string | number)[]; // Corresponds to the 'pages' key (list of pages)
};

export interface ChatMessage {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;         // ✅ use Date instead of number
  originalContent?: string;
  traceId: string;
  spanId?: string;
  Citation?: Citation[];
  images?: string[];
  detected_intent?: string;
};

export interface Chatbot {
  id: string;
  name: string;
  description: string;
  documents: string[];
  createdAt: Date;
  datastoreId: number;
  datastoreName: string;
}

export interface CreateChatbotDataResponse {
  id: number,
  name: string;
  description: string;
  created_at?: string;
  datastore_id: number;
  intents?: { title: string; description: string }[];
}

export interface CreateDatastoreData {
  id: number,
  name: string;
  description: string;
  documents?: File[];
  updatedAt?: string;
  embeddingModel?: string;
  embeddingProvider?: string;
  vectorStoreProvider?: string;
  similarityMetric?: string;
  documentCount?: number;
  rootFolderId?: number;
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

//Replaced by DocumentRecord - Ankit
export interface FileRecord {
  id: number;
  filename: string;
  content_type: string;
  size: number;
  datastore_id: number;
  uploaded_at: string;
}

export interface DocumentRecord {
  id: number;
  filename: string;
  // content_type: string;
  // size: number;
  datastore_id: number;
  uploaded_at: string;
  insert_vector_status: boolean
}

// Simple mapping of common extensions to MIME types
export const mimeTypes = {
  pdf: "application/pdf",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  gif: "image/gif",
  txt: "text/plain",
  csv: "text/csv",
  json: "application/json",
  html: "text/html",
  doc: "application/msword",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xls: "application/vnd.ms-excel",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  mp3: "audio/mpeg",
  mp4: "video/mp4",
  zip: "application/zip",
};

export function getMimeTypeFromName(fileName: string) {
  const ext = fileName.split(".").pop().toLowerCase();
  return mimeTypes[ext] || "application/octet-stream"; // fallback generic binary type
}