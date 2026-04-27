import { CreateAgentDialog } from "@/features/create-agent/ui/create-agent-dialog";
import { AgentDashboard } from "@/widgets/agent-dashboard/ui/agent-dashboard";

export default function AgentsPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create and manage your accountant agents.
          </p>
        </div>
        <CreateAgentDialog />
      </div>

      <AgentDashboard />
    </section>
  );
}

