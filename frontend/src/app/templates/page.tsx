"use client";

import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Plus, FileText, Eye, Edit2, Copy } from "lucide-react";
import { getTemplates, createTemplate } from "@/lib/api";
import { EmailTemplate } from "@/types";
import { formatDate } from "@/lib/format";
import { toast } from "sonner";

const AVAILABLE_VARIABLES = [
  { label: "First Name", value: "{{contact.first_name}}" },
  { label: "Last Name", value: "{{contact.last_name}}" },
  { label: "Role", value: "{{contact.role}}" },
  { label: "District Name", value: "{{district.name}}" },
  { label: "District State", value: "{{district.state}}" },
  { label: "ELL Students", value: "{{district.ell_students}}" },
  { label: "Total Students", value: "{{district.total_students}}" },
  { label: "Sender Name", value: "{{sender.name}}" },
  { label: "Sender Title", value: "{{sender.title}}" },
  { label: "Sender Company", value: "{{sender.company}}" },
];

const SAMPLE_DATA: Record<string, string> = {
  "{{contact.first_name}}": "Mike",
  "{{contact.last_name}}": "Miles",
  "{{contact.role}}": "Superintendent",
  "{{district.name}}": "Houston Independent School District",
  "{{district.state}}": "Texas",
  "{{district.ell_students}}": "62,221",
  "{{district.total_students}}": "196,943",
  "{{sender.name}}": "Jane Smith",
  "{{sender.title}}": "VP of Partnerships",
  "{{sender.company}}": "EduTech Solutions",
};

function replaceVariables(text: string): string {
  let result = text;
  Object.entries(SAMPLE_DATA).forEach(([key, val]) => {
    result = result.replace(new RegExp(key.replace(/[{}]/g, "\\$&"), "g"), val);
  });
  return result;
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<EmailTemplate | null>(null);
  const [editName, setEditName] = useState("");
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function load() {
      const data = await getTemplates();
      setTemplates(data);
      setLoading(false);
    }
    load();
  }, []);

  function openNew() {
    setEditName("");
    setEditSubject("");
    setEditBody("");
    setDialogOpen(true);
  }

  function insertVariable(variable: string) {
    setEditBody((prev) => prev + variable);
  }

  async function handleSave() {
    if (!editName.trim() || !editSubject.trim() || !editBody.trim()) {
      toast.error("All fields are required");
      return;
    }
    setSaving(true);
    const t = await createTemplate({
      name: editName.trim(),
      subject: editSubject.trim(),
      body: editBody.trim(),
    });
    setTemplates((prev) => [t, ...prev]);
    setDialogOpen(false);
    setSaving(false);
    toast.success("Template created");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Email Templates</h1>
          <p className="text-muted-foreground">
            Create and manage email templates for your campaigns.
          </p>
        </div>
        <Button onClick={openNew}>
          <Plus className="mr-1 h-4 w-4" />
          New Template
        </Button>
      </div>

      {/* Template List */}
      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-32 animate-pulse rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : templates.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground" />
            <p className="mt-4 text-muted-foreground">
              No templates yet. Create your first one.
            </p>
            <Button className="mt-4" onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Create Template
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {templates.map((t) => (
            <Card key={t.id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-base">{t.name}</CardTitle>
                    <CardDescription className="mt-1">
                      Subject: {t.subject}
                    </CardDescription>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPreviewTemplate(t)}
                    >
                      <Eye className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setEditName(t.name + " (copy)");
                        setEditSubject(t.subject);
                        setEditBody(t.body);
                        setDialogOpen(true);
                      }}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="line-clamp-3 text-sm text-muted-foreground whitespace-pre-line">
                  {t.body}
                </p>
                <Separator className="my-3" />
                <div className="flex items-center justify-between">
                  <div className="flex flex-wrap gap-1">
                    {t.variables.slice(0, 3).map((v) => (
                      <Badge key={v} variant="secondary" className="text-xs">
                        {v}
                      </Badge>
                    ))}
                    {t.variables.length > 3 && (
                      <Badge variant="secondary" className="text-xs">
                        +{t.variables.length - 3} more
                      </Badge>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {formatDate(t.updatedAt)}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editName ? "Edit Template" : "Create Template"}
            </DialogTitle>
            <DialogDescription>
              Write your email template. Use variables to personalize.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                Template Name
              </label>
              <Input
                placeholder="e.g. Initial Outreach"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium">
                Subject Line
              </label>
              <Input
                placeholder='e.g. Improving ELL outcomes at {{district.name}}'
                value={editSubject}
                onChange={(e) => setEditSubject(e.target.value)}
              />
            </div>
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <label className="text-sm font-medium">Body</label>
                <DropdownMenu>
                  <DropdownMenuTrigger
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                  >
                    <Edit2 className="mr-1 h-3 w-3" />
                    Insert Variable
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {AVAILABLE_VARIABLES.map((v) => (
                      <DropdownMenuItem
                        key={v.value}
                        onClick={() => insertVariable(v.value)}
                      >
                        <span className="mr-2 text-muted-foreground">
                          {v.value}
                        </span>
                        {v.label}
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <Textarea
                placeholder="Write your email body here..."
                value={editBody}
                onChange={(e) => setEditBody(e.target.value)}
                rows={10}
                className="font-mono text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save Template"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview Dialog */}
      <Dialog
        open={!!previewTemplate}
        onOpenChange={() => setPreviewTemplate(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Preview: {previewTemplate?.name}</DialogTitle>
            <DialogDescription>
              Preview with sample data substituted for variables.
            </DialogDescription>
          </DialogHeader>
          {previewTemplate && (
            <div className="space-y-4 py-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">
                  Subject
                </label>
                <p className="text-sm font-medium">
                  {replaceVariables(previewTemplate.subject)}
                </p>
              </div>
              <Separator />
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">
                  Body
                </label>
                <div className="rounded-md border bg-muted/30 p-4">
                  <p className="whitespace-pre-line text-sm">
                    {replaceVariables(previewTemplate.body)}
                  </p>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-muted-foreground">
                  Variables Used
                </label>
                <div className="flex flex-wrap gap-1">
                  {previewTemplate.variables.map((v) => (
                    <Badge key={v} variant="secondary" className="text-xs">
                      {v}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPreviewTemplate(null)}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
