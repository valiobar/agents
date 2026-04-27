"use client";

import { Pencil } from "lucide-react";
import { useState } from "react";

import type { Agent } from "@/entities/agent/model/types";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";

import { UpdateAgentForm } from "./update-agent-form";

export function UpdateAgentDialog({ agent }: Readonly<{ agent: Agent }>) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={(event) => event.stopPropagation()}
        >
          <Pencil className="mr-2 h-4 w-4" />
          Edit
        </Button>
      </DialogTrigger>

      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit agent</DialogTitle>
          <DialogDescription>Update company assignment and model settings.</DialogDescription>
        </DialogHeader>

        <UpdateAgentForm
          agent={agent}
          onSuccess={() => setOpen(false)}
          onCancel={() => setOpen(false)}
        />
      </DialogContent>
    </Dialog>
  );
}
