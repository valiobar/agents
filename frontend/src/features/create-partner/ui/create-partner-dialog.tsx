"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/shared/ui/dialog";

import { CreatePartnerForm } from "./create-partner-form";

interface CreatePartnerDialogProps {
  defaultCompanyId?: string;
}

export function CreatePartnerDialog({ defaultCompanyId }: Readonly<CreatePartnerDialogProps>) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" />
          Create partner
        </Button>
      </DialogTrigger>

      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create partner</DialogTitle>
          <DialogDescription>Add a client, supplier, or other company-scoped counterparty.</DialogDescription>
        </DialogHeader>

        <CreatePartnerForm
          key={defaultCompanyId ?? "no-company"}
          defaultCompanyId={defaultCompanyId}
          onSuccess={() => setOpen(false)}
          onCancel={() => setOpen(false)}
        />
      </DialogContent>
    </Dialog>
  );
}
