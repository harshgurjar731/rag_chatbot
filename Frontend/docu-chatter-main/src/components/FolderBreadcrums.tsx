type Folder = {
  id: number;
  name: string;
};

type FolderBreadcrumbsProps = {
  breadcrumbs: Folder[];
  onNavigate: (folderId: number) => void;
};

export default function FolderBreadcrumbs({ breadcrumbs, onNavigate }: FolderBreadcrumbsProps) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
    <p> 📁 </p>
      {breadcrumbs.map((folder, index) => (
        <div key={folder.id} className="flex items-center gap-2">
          <button
            onClick={() => onNavigate(folder.id)}
            className="hover:text-foreground underline underline-offset-4 transition-colors"
          >
            {folder.name}
          </button>

          {index < breadcrumbs.length - 1 && (
            <span className="text-muted-foreground">/</span>
          )}
        </div>
      ))}
    </div>
  );
}
