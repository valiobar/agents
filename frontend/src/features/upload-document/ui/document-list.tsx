"use client";

import { FileText } from "lucide-react";
import { useSession } from "next-auth/react";
import { useEffect, useMemo, useState } from "react";

import { useCompanies } from "@/entities/company/api/queries";
import { formatDate, formatFileSize } from "@/shared/lib/format";
import { Badge } from "@/shared/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";

import { useDocuments } from "../api/mutations";
import type { DocumentResponse, DocumentStatus } from "../model/types";

const statusLabels: Record<DocumentStatus, string> = {
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
  deleted: "Deleted",
};

function getStatusBadgeVariant(status: DocumentStatus) {
  if (status === "ready") return "default";
  if (status === "failed") return "outline";
  return "secondary";
}

function DocumentStatusBadge({ status }: Readonly<{ status: DocumentStatus }>) {
  const variant = getStatusBadgeVariant(status);

  return (
    <Badge
      variant={variant}
      className={status === "failed" ? "border-destructive text-destructive" : undefined}
    >
      {statusLabels[status]}
    </Badge>
  );
}

function DocumentListItem({ document }: Readonly<{ document: DocumentResponse }>) {
  return (
    <li className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
        <div className="min-w-0">
          <p className="truncate font-medium">{document.filename}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {document.content_type} - {formatFileSize(document.size_bytes)} -{" "}
            {document.chunk_count} chunks
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Uploaded {formatDate(document.created_at)}
          </p>
        </div>
      </div>
      <DocumentStatusBadge status={document.status} />
    </li>
  );
}

export function DocumentList() {
  const { data: session, status } = useSession();
  const companies = useCompanies(session?.accessToken);
  const [companyId, setCompanyId] = useState("");

  const defaultCompanyId = useMemo(() => {
    const companyList = companies.data ?? [];
    return companyList.find((company) => company.is_default)?.id ?? companyList[0]?.id ?? "";
  }, [companies.data]);

  useEffect(() => {
    if (!companyId && defaultCompanyId) {
      setCompanyId(defaultCompanyId);
    }
  }, [companyId, defaultCompanyId]);

  const documents = useDocuments(session?.accessToken, {
    company_id: companyId || undefined,
    limit: 50,
    offset: 0,
  });

  if (status === "loading" || companies.isLoading || documents.isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
          <Spinner />
          <span>Loading documents...</span>
        </CardContent>
      </Card>
    );
  }

  if (!companies.data?.length) {
    return (
      <Card>
        <CardContent className="p-6">
          <EmptyState
            title="Create a company first"
            description="Knowledge documents are scoped to a company."
          />
        </CardContent>
      </Card>
    );
  }

  if (documents.isError) {
    return (
      <Card>
        <CardContent className="p-6">
          <EmptyState
            title="Unable to load documents"
            description="Refresh the page or try again after signing in."
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Knowledge Documents</CardTitle>
        <CardDescription>
          Recently uploaded files available to retrieval workflows.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Company</p>
          <Select value={companyId} onValueChange={setCompanyId}>
            <SelectTrigger>
              <SelectValue placeholder="Select company" />
            </SelectTrigger>
            <SelectContent>
              {companies.data.map((company) => (
                <SelectItem key={company.id} value={company.id}>
                  {company.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {documents.data?.length ? (
          <ul className="space-y-3">
            {documents.data.map((document) => (
              <DocumentListItem key={document.id} document={document} />
            ))}
          </ul>
        ) : (
          <EmptyState
            title="No documents uploaded"
            description="Upload a PDF, text, or Markdown file to make it available for retrieval."
          />
        )}
      </CardContent>
    </Card>
  );
}
