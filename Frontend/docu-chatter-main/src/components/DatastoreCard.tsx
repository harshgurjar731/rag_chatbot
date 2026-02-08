import { Calendar, FileText, MessageCircle, Trash } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Chatbot, CreateDatastoreData } from '@/types/chatbot';
import { cn } from '@/lib/utils';
import { useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '@/constants';

interface DatastoreCardProps {
  data: CreateDatastoreData;
  onClick: () => void;
  onDelete: () => void;

}

export const DatastoreCard = ({ data, onClick, onDelete }: DatastoreCardProps) => {
  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(date);
  };

  const deleteDatastore = async() => {
    console.log("hello Rupali")
    const response = await axios.post(`${API_BASE_URL}/ingestion/deleteDatastore/${data.id}`);
    console.log(response.data)
    onDelete()
  }

  useEffect(() => {
    console.log("DatastoreCard updatedAt:", data.updatedAt);
  }, [data.updatedAt]);

  return (
    <Card 
      className="cursor-pointer transition-all duration-300 hover:shadow-card-custom hover:scale-105 bg-gradient-card border-chatbot-primary/20 group"
      onClick={onClick}
    >
       {/* ✅ DELETE ICON */}
      <div className='relative'>
      <button
        onClick={(e) => {
          e.stopPropagation(); // prevent card click
          deleteDatastore();
        }}
        className="absolute top-2 right-2 z-20 rounded-md opacity-0 group-hover:opacity-100
              transition-opacity duration-300 ease-in-out hover:bg-chatbot-primary/15 hover:scale-110"
      >
        <Trash className="w-4 h-4 text-chatbot-primary" />
      </button>
      </div>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div>
              <CardTitle className="text-lg font-semibold text-foreground group-hover:text-chatbot-primary transition-colors">
                {data.name}
              </CardTitle>
              <CardDescription className="text-muted-foreground mt-1">
                {data.description}
              </CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <FileText className="h-3 w-3" />
              <span>{data.documentCount ?? 0} docs</span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            <span>{data?.updatedAt
    ? new Date(data.updatedAt).toLocaleDateString("en-GB").replace(/\//g, "-")
    : ""}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};