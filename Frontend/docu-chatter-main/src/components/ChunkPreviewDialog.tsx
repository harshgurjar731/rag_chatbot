import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useEffect } from "react";

interface ChunkPreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  chunks: Array<string>;
}

export const ChunkPreviewDialog = ({
  open,
  onOpenChange,
  chunks,
}: ChunkPreviewDialogProps) => {

  useEffect(() => {
    console.log("Chunks on load: ", chunks)
  }, [])

  useEffect(() => {
    if(open){
      console.log("Chunks on open: ", chunks)
    }
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="text-2xl">Chunk Preview ({chunks.length} chunks)</DialogTitle>
        </DialogHeader>

        <ScrollArea className="h-[70vh] pr-4">
          <div className="grid grid-cols-2 gap-4">
            {chunks.map((chunk, index) => (
              <div key={index} className="p-4 rounded-lg border bg-card space-y-2">
                <div className="font-semibold text-sm">
                  #{index+1}. Characters: {chunk.characters}
                </div>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">{chunk}</p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};
