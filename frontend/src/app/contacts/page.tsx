"use client";

import { useEffect, useState, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Download,
  Mail,
  Send,
} from "lucide-react";
import { getContacts } from "@/lib/api";
import { Contact, ContactFilters, ContactRole, EmailStatus } from "@/types";
import { US_STATES } from "@/lib/mock-data";
import { toast } from "sonner";

const roles: ContactRole[] = [
  "Superintendent",
  "Assistant Superintendent",
  "Director of ELL",
  "Curriculum Director",
  "Principal",
  "Other",
];

const emailStatuses: EmailStatus[] = [
  "verified",
  "unverified",
  "bounced",
  "catch_all",
  "unknown",
];

const emailStatusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  verified: "default",
  unverified: "secondary",
  bounced: "destructive",
  catch_all: "outline",
  unknown: "outline",
};

export default function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState<ContactFilters>({
    search: "",
    role: "",
    emailStatus: "",
    state: "",
    page: 1,
    pageSize: 20,
  });

  const load = useCallback(async () => {
    setLoading(true);
    const clean: ContactFilters = { ...filters };
    if (!clean.search) delete clean.search;
    if (!clean.role) delete clean.role;
    if (!clean.emailStatus) delete clean.emailStatus;
    if (!clean.state) delete clean.state;
    const res = await getContacts(clean);
    setContacts(res.data);
    setTotal(res.total);
    setTotalPages(res.totalPages);
    setLoading(false);
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  function updateFilter<K extends keyof ContactFilters>(
    key: K,
    value: ContactFilters[K]
  ) {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (selected.size === contacts.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(contacts.map((c) => c.id)));
    }
  }

  function handleBulkAction(action: string) {
    if (selected.size === 0) {
      toast.error("No contacts selected");
      return;
    }
    switch (action) {
      case "campaign":
        toast.success(`Added ${selected.size} contacts to campaign`);
        break;
      case "verify":
        toast.success(`Queued ${selected.size} contacts for email verification`);
        break;
      case "export":
        toast.success(`Exported ${selected.size} contacts to CSV`);
        break;
    }
    setSelected(new Set());
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Contacts</h1>
          <p className="text-muted-foreground">
            Manage superintendents and district contacts.
          </p>
        </div>
        {selected.size > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger
              className={cn(buttonVariants({ variant: "default" }))}
            >
              Bulk Actions ({selected.size})
              <ChevronDown className="ml-1 h-4 w-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleBulkAction("campaign")}>
                <Send className="mr-2 h-4 w-4" />
                Add to Campaign
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleBulkAction("verify")}>
                <Mail className="mr-2 h-4 w-4" />
                Verify Emails
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleBulkAction("export")}>
                <Download className="mr-2 h-4 w-4" />
                Export CSV
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-[200px] flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search contacts, emails, districts..."
                value={filters.search ?? ""}
                onChange={(e) => updateFilter("search", e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={filters.role ?? ""}
              onValueChange={(v) => {
                const val = v as string | null;
                updateFilter("role", !val || val === "all" ? "" : (val as ContactRole));
              }}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                {roles.map((r) => (
                  <SelectItem key={r} value={r}>
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={filters.emailStatus ?? ""}
              onValueChange={(v) => {
                const val = v as string | null;
                updateFilter(
                  "emailStatus",
                  !val || val === "all" ? "" : (val as EmailStatus)
                );
              }}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Email Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                {emailStatuses.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={filters.state ?? ""}
              onValueChange={(v) => {
                const val = v as string | null;
                updateFilter("state", !val || val === "all" ? "" : val);
              }}
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="State" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All States</SelectItem>
                {US_STATES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setFilters({
                  search: "",
                  role: "",
                  emailStatus: "",
                  state: "",
                  page: 1,
                  pageSize: 20,
                });
                setSelected(new Set());
              }}
            >
              Clear
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">
            {total} Contacts
          </CardTitle>
          <CardDescription>
            Select contacts for bulk actions.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-6">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="h-12 animate-pulse rounded bg-muted"
                />
              ))}
            </div>
          ) : contacts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <p className="text-muted-foreground">
                No contacts match your filters.
              </p>
              <Button
                variant="link"
                onClick={() =>
                  setFilters({
                    search: "",
                    role: "",
                    emailStatus: "",
                    state: "",
                    page: 1,
                    pageSize: 20,
                  })
                }
              >
                Clear all filters
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40px]">
                    <input
                      type="checkbox"
                      checked={
                        contacts.length > 0 &&
                        selected.size === contacts.length
                      }
                      onChange={toggleAll}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                  </TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>District</TableHead>
                  <TableHead className="w-[60px]">State</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead className="text-right">Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contacts.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={selected.has(c.id)}
                        onChange={() => toggleSelect(c.id)}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                    </TableCell>
                    <TableCell className="font-medium">
                      {c.firstName} {c.lastName}
                    </TableCell>
                    <TableCell className="text-sm">{c.role}</TableCell>
                    <TableCell className="text-sm">{c.districtName}</TableCell>
                    <TableCell>{c.state}</TableCell>
                    <TableCell className="text-sm">{c.email}</TableCell>
                    <TableCell>
                      <Badge
                        variant={emailStatusVariant[c.emailStatus] ?? "outline"}
                      >
                        {c.emailStatus}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{c.phone}</TableCell>
                    <TableCell className="text-right">
                      <span
                        className={
                          c.confidenceScore >= 80
                            ? "font-medium text-green-600"
                            : c.confidenceScore >= 50
                              ? "font-medium text-yellow-600"
                              : "font-medium text-red-600"
                        }
                      >
                        {c.confidenceScore}%
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t px-6 py-3">
            <p className="text-sm text-muted-foreground">
              Page {filters.page} of {totalPages}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={filters.page === 1}
                onClick={() =>
                  setFilters((p) => ({ ...p, page: (p.page ?? 1) - 1 }))
                }
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={filters.page === totalPages}
                onClick={() =>
                  setFilters((p) => ({ ...p, page: (p.page ?? 1) + 1 }))
                }
              >
                Next
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
