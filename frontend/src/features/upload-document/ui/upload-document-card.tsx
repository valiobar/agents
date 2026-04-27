"use client";

import { UploadCloud } from "lucide-react";
import { useSession } from "next-auth/react";
import { useEffect, useMemo, useRef, useState } from "react";

import { useCompanies } from "@/entities/company/api/queries";
import { formatFileSize } from "@/shared/lib/format";
import { Alert, AlertDescription } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";

import { getDocumentUploadErrorMessage, useUploadDocument } from "../api/mutations";
import {
  MAX_DOCUMENT_SIZE_BYTES,
  supportedDocumentTypes,
  uploadDocumentSchema,
} from "../model/schema";

const acceptedDocumentTypes = [
  ".pdf",
  ".txt",
  ".md",
  ".markdown",
  ...supportedDocumentTypes,
].join(",");

export function UploadDocumentCard() {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);
  const upload = useUploadDocument(session?.accessToken);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [companyId, setCompanyId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const defaultCompanyId = useMemo(() => {
    const companyList = companies.data ?? [];
    return companyList.find((company) => company.is_default)?.id ?? companyList[0]?.id ?? "";
  }, [companies.data]);

  useEffect(() => {
    if (!companyId && defaultCompanyId) {
      setCompanyId(defaultCompanyId);
    }
  }, [companyId, defaultCompanyId]);

  async function onFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setError(null);
    setSuccess(null);

    if (!file) return;

    const result = uploadDocumentSchema.safeParse({ file, company_id: companyId });
    if (!result.success) {
      setError(result.error.issues[0]?.message ?? "Select a supported document.");
      event.target.value = "";
      return;
    }

    try {
      const document = await upload.mutateAsync(result.data);
      setSuccess(`${document.filename} uploaded and queued for retrieval.`);
      event.target.value = "";
    } catch (err) {
      setError(getDocumentUploadErrorMessage(err));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Knowledge Document</CardTitle>
        <CardDescription>
          Add PDF, text, or Markdown files for retrieval. Max size{" "}
          {formatFileSize(MAX_DOCUMENT_SIZE_BYTES)}.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Company</p>
          <Select value={companyId} onValueChange={setCompanyId} disabled={companies.isLoading}>
            <SelectTrigger>
              <SelectValue placeholder="Select company" />
            </SelectTrigger>
            <SelectContent>
              {companies.data?.map((company) => (
                <SelectItem key={company.id} value={company.id}>
                  {company.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Input
            ref={fileInputRef}
            type="file"
            accept={acceptedDocumentTypes}
            disabled={upload.isPending || !session?.accessToken || !companyId}
            onChange={onFileChange}
          />
          <Button
            type="button"
            variant="outline"
            disabled={upload.isPending || !session?.accessToken || !companyId}
            onClick={() => fileInputRef.current?.click()}
          >
            {upload.isPending ? (
              <>
                <Spinner className="mr-2" />
                Uploading
              </>
            ) : (
              <>
                <UploadCloud className="mr-2 h-4 w-4" />
                Choose File
              </>
            )}
          </Button>
        </div>

        {session?.accessToken ? null : (
          <Alert variant="destructive">
            <AlertDescription>Sign in before uploading documents.</AlertDescription>
          </Alert>
        )}

        {session?.accessToken && !companies.isLoading && !companies.data?.length ? (
          <Alert variant="destructive">
            <AlertDescription>Create a company before uploading knowledge documents.</AlertDescription>
          </Alert>
        ) : null}

        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        {success ? (
          <Alert>
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}
