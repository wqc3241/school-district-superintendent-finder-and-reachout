"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Plus } from "lucide-react";
import { getCampaigns, createCampaign } from "@/lib/api";
import { Campaign } from "@/types";
import { formatNumber, formatDate } from "@/lib/format";
import { toast } from "sonner";

const statusVariant: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  active: "default",
  draft: "secondary",
  paused: "outline",
  completed: "default",
};

const statusColor: Record<string, string> = {
  active: "",
  draft: "",
  paused: "",
  completed: "bg-green-600 hover:bg-green-600",
};

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    async function load() {
      const data = await getCampaigns();
      setCampaigns(data);
      setLoading(false);
    }
    load();
  }, []);

  async function handleCreate() {
    if (!newName.trim()) {
      toast.error("Campaign name is required");
      return;
    }
    setCreating(true);
    const c = await createCampaign({
      name: newName.trim(),
      description: newDesc.trim(),
    });
    setCampaigns((prev) => [c, ...prev]);
    setDialogOpen(false);
    setNewName("");
    setNewDesc("");
    setCreating(false);
    toast.success("Campaign created");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Campaigns</h1>
          <p className="text-muted-foreground">
            Manage your outreach campaigns and sequences.
          </p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger
            className={cn(buttonVariants({ variant: "default" }))}
          >
            <Plus className="mr-1 h-4 w-4" />
            New Campaign
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create Campaign</DialogTitle>
              <DialogDescription>
                Start a new outreach campaign. You can add contacts and
                sequences after creation.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Name
                </label>
                <Input
                  placeholder="e.g. Q2 2025 - Texas Districts"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Description
                </label>
                <Textarea
                  placeholder="Describe the goal and target audience..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={creating}>
                {creating ? "Creating..." : "Create Campaign"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Summary */}
      <div className="grid gap-4 sm:grid-cols-4">
        {[
          {
            label: "Total Campaigns",
            value: campaigns.length,
          },
          {
            label: "Active",
            value: campaigns.filter((c) => c.status === "active").length,
          },
          {
            label: "Total Enrolled",
            value: campaigns.reduce((s, c) => s + c.enrolled, 0),
          },
          {
            label: "Total Replies",
            value: campaigns.reduce((s, c) => s + c.replied, 0),
          },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p className="mt-1 text-2xl font-bold">{formatNumber(s.value)}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">All Campaigns</CardTitle>
          <CardDescription>
            Click a campaign to view details and manage sequences.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-6">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-12 animate-pulse rounded bg-muted"
                />
              ))}
            </div>
          ) : campaigns.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <p className="text-muted-foreground">
                No campaigns yet. Create your first one.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Campaign</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Enrolled</TableHead>
                  <TableHead className="text-right">Sent</TableHead>
                  <TableHead className="text-right">Opened</TableHead>
                  <TableHead className="text-right">Clicked</TableHead>
                  <TableHead className="text-right">Replied</TableHead>
                  <TableHead className="text-right">Bounced</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {campaigns.map((c) => (
                  <TableRow key={c.id} className="cursor-pointer">
                    <TableCell>
                      <Link
                        href={`/campaigns/${c.id}`}
                        className="font-medium hover:underline"
                      >
                        {c.name}
                      </Link>
                      <p className="mt-0.5 max-w-xs truncate text-xs text-muted-foreground">
                        {c.description}
                      </p>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={statusVariant[c.status]}
                        className={statusColor[c.status]}
                      >
                        {c.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {formatNumber(c.enrolled)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatNumber(c.sent)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatNumber(c.opened)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatNumber(c.clicked)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatNumber(c.replied)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatNumber(c.bounced)}
                    </TableCell>
                    <TableCell className="text-sm">
                      {formatDate(c.createdAt)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
