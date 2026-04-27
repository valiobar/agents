import { DocumentList } from "@/features/upload-document/ui/document-list";
import { UploadDocumentCard } from "@/features/upload-document/ui/upload-document-card";
import { AgentDashboard } from "@/widgets/agent-dashboard/ui/agent-dashboard";

export default function DashboardHomePage() {
  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Your agents and financial workflows in one place.
        </p>
      </div>

      <AgentDashboard />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,28rem)]">
        <DocumentList />
        <UploadDocumentCard />
      </div>
    </section>
  );
}

