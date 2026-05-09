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

import { CreateInventoryItemForm } from "./create-inventory-item-form";

interface CreateInventoryItemDialogProps {
  companyId: string;
  token: string;
}

export function CreateInventoryItemDialog({
  companyId,
  token,
}: Readonly<CreateInventoryItemDialogProps>) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" />
          New item
        </Button>
      </DialogTrigger>

      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create inventory item</DialogTitle>
          <DialogDescription>Add an inventory SKU with optional stock planning values.</DialogDescription>
        </DialogHeader>

        <CreateInventoryItemForm companyId={companyId} token={token} onSuccess={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}
