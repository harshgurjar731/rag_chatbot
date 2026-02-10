import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { LogOut } from "lucide-react";

type LogoutDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
};

export function LogoutDialog({
  open,
  onOpenChange,
  onConfirm,
}: LogoutDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[420px] bg-gradient-card border-chatbot-primary/20">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <LogOut className="h-5 w-5 text-chatbot-primary" />
            Confirm Logout
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to log out? You will need to sign in again to
            access the application.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-3 pt-4">
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            variant="chatbot"
            className="flex-1"
            onClick={onConfirm}
          >
            Logout
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
