"use client";

import { ArrowRightLeft } from "lucide-react";
import { useState } from "react";

import { Button } from "@/shared/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/shared/ui/dialog";

import { RecordStockMovementForm } from "./record-stock-movement-form";

export interface RecordStockMovementDialogProps {
  companyId: string;
  token: string;
}

export function RecordStockMovementDialog({
  companyId,
  token,
}: Readonly<RecordStockMovementDialogProps>) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          <ArrowRightLeft className="mr-1.5 h-4 w-4" />
          Record Movement
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Record Stock Movement</DialogTitle>
        </DialogHeader>
        <RecordStockMovementForm companyId={companyId} token={token} onSuccess={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  );
}
