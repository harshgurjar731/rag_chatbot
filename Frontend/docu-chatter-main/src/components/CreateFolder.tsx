import { useState } from "react";
import { Button } from "@/components/ui/button";
import { FolderPlus } from "lucide-react";
import { API_BASE_URL } from "@/constants";

type CreateFolderProps = {
  currentFolderId: number;
  onCreated: () => void;
};

export default function CreateFolderDialog({ currentFolderId, onCreated }: CreateFolderProps) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  async function createFolder() {
    if (!name.trim()) return;

    setLoading(true);

    await fetch(`${API_BASE_URL}/ingestion/folders`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        parent_id: currentFolderId
      })
    });

    setLoading(false);
    setName("");
    setOpen(false);
    onCreated();
  }

  return (
    <>
      {/* Trigger */}
      <button 
        onClick={() => setOpen(true)}
        className="pl-4 text-sm text-muted-foreground cursor-pointer hover:text-foreground">
          + Create Folder
      </button>

      {/* Overlay */}
      {open && (
        <div className="fixed inset-0 bg-background/60 backdrop-blur-sm flex items-center justify-center z-50">
          
          {/* Dialog card */}
          <div className="bg-card border rounded-lg shadow-lg w-full max-w-md p-6">

            <h2 className="text-xl font-semibold text-foreground mb-2">
              Create new folder
            </h2>
            <p className="text-sm text-muted-foreground mb-4">
              Organize your documents into folders
            </p>

            <input
              className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              placeholder="Folder name"
              value={name}
              onChange={e => setName(e.target.value)}
              autoFocus
            />

            <div className="flex justify-end gap-2 mt-6">
              <Button
                variant="ghost"
                onClick={() => setOpen(false)}
              >
                Cancel
              </Button>

              <Button
                variant="chatbot"
                disabled={loading}
                onClick={createFolder}
              >
                {loading ? "Creating..." : "Create folder"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
