import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const splitterTypes = [
  { value: "none", label: "None" },
  { value: "character", label: "Character Text Splitter" },
  { value: "code", label: "Code Text Splitter" },
  { value: "html-to-markdown", label: "HtmlToMarkdown Text Splitter" },
  { value: "markdown", label: "Markdown Text Splitter" },
  { value: "recursive", label: "Recursive Character Text Splitter" },
  { value: "token", label: "Token Text Splitter" },
];

interface TextSplitterSelectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (splitter: string, config: any) => void;
}

export const TextSplitterSelectionDialog = ({
  open,
  onOpenChange,
  onSelect,
}: TextSplitterSelectionDialogProps) => {
  const [selectedSplitter, setSelectedSplitter] = useState("recursive");
  const [chunkSize, setChunkSize] = useState("1000");
  const [chunkOverlap, setChunkOverlap] = useState("200");
  const [customSeparators, setCustomSeparators] = useState("");

  const handleConfirm = () => {
    const config = {
      chunkSize: parseInt(chunkSize),
      chunkOverlap: parseInt(chunkOverlap),
      customSeparators,
    };
    onSelect(splitterTypes.find(s => s.value === selectedSplitter)?.value, config);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <DialogTitle className="text-2xl">Select Text Splitter</DialogTitle>
            <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-xl">
              ✂️
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-6">
          {/* Splitter Selection */}
          <div className="space-y-2">
            <Label>Splitter</Label>
            <Select value={selectedSplitter} onValueChange={setSelectedSplitter}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {splitterTypes.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selectedSplitter !== "none" && (
            <>
              {/* Chunk Size */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Label htmlFor="chunkSize">Chunk Size</Label>
                  <div className="w-4 h-4 rounded-full bg-muted flex items-center justify-center text-xs">
                    ℹ️
                  </div>
                </div>
                <Input
                  id="chunkSize"
                  type="number"
                  value={chunkSize}
                  onChange={(e) => setChunkSize(e.target.value)}
                  placeholder="1000"
                />
              </div>

              {/* Chunk Overlap */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Label htmlFor="chunkOverlap">Chunk Overlap</Label>
                  <div className="w-4 h-4 rounded-full bg-muted flex items-center justify-center text-xs">
                    ℹ️
                  </div>
                </div>
                <Input
                  id="chunkOverlap"
                  type="number"
                  value={chunkOverlap}
                  onChange={(e) => setChunkOverlap(e.target.value)}
                  placeholder="200"
                />
              </div>

              {/* Custom Separators */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Label htmlFor="separators">Custom Separators</Label>
                  <div className="w-4 h-4 rounded-full bg-muted flex items-center justify-center text-xs">
                    ℹ️
                  </div>
                </div>
                <Textarea
                  id="separators"
                  value={customSeparators}
                  onChange={(e) => setCustomSeparators(e.target.value)}
                  placeholder="e.g., \n\n, \n, , ."
                  rows={3}
                />
              </div>
            </>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} className="bg-primary hover:bg-primary/90">
            Confirm
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
