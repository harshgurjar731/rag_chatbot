import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ChunkPreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  chunks: Array<{ id: number; characters: number; content: string }>;
}

export const ChunkPreviewDialog = ({
  open,
  onOpenChange,
  chunks,
}: ChunkPreviewDialogProps) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="text-2xl">Chunk Preview ({chunks.length} chunks)</DialogTitle>
        </DialogHeader>

        <ScrollArea className="h-[70vh] pr-4">
          <div className="grid grid-cols-2 gap-4">
            {chunks.map((chunk) => (
              <div key={chunk.id} className="p-4 rounded-lg border bg-card space-y-2">
                <div className="font-semibold text-sm">
                  #{chunk.id}. Characters: {chunk.characters}
                </div>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">{chunk.content}</p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};
