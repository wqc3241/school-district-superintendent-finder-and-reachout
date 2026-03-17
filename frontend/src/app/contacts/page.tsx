"use client";

import { useEffect, useState, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { SortableHeader } from "@/components/sortable-header";
import { useSort } from "@/hooks/use-sort";
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
  ChevronDown,
  Download,
  Mail,
  Send,
} from "lucide-react";
import { getContacts } from "@/lib/api";
import { Contact, ContactFilters } from "@/types";
import { toast } from "sonner";
import { Pagination } from "@/components/pagination";
import { exportToCsv } from "@/lib/export-csv";

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
  const [stateOptions, setStateOptions] = useState<string[]>([]);
  const [roleOptions, setRoleOptions] = useState<string[]>([]);
  const [emailStatusOptions, setEmailStatusOptions] = useState<string[]>([]);
  const [filters, setFilters] = useState<ContactFilters>({
    search: "",
    role: "",
    emailStatus: "",
    state: "",
    page: 1,
    pageSize: 20,
  });

  const { sort, handleSort, sortedData: sortedContacts } = useSort(contacts);

  useEffect(() => {
    fetch("/api/filter-options")
      .then(r => r.json())
      .then(data => {
        setStateOptions(data.states || []);
        setRoleOptions(data.roles || []);
        setEmailStatusOptions(data.emailStatuses || []);
      })
      .catch(() => {});
  }, []);

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
      case "export": {
        const selectedContacts = contacts.filter((c) => selected.has(c.id));
        exportToCsv(
          "contacts.csv",
          selectedContacts.map((c) => ({
            first_name: c.firstName,
            last_name: c.lastName,
            role: c.role,
            district: c.districtName,
            state: c.state,
            email: c.email,
            email_status: c.emailStatus,
            phone: c.phone,
            confidence_score: c.confidenceScore,
          })),
          [
            { key: "first_name", label: "First Name" },
            { key: "last_name", label: "Last Name" },
            { key: "role", label: "Role" },
            { key: "district", label: "District" },
            { key: "state", label: "State" },
            { key: "email", label: "Email" },
            { key: "email_status", label: "Email Status" },
            { key: "phone", label: "Phone" },
            { key: "confidence_score", label: "Confidence Score" },
          ]
        );
        toast.success(`Exported ${selectedContacts.length} contacts to CSV`);
        break;
      }
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
                updateFilter("role", !val || val === "all" ? "" : val);
              }}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Role" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Roles</SelectItem>
                {roleOptions.map((r) => (
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
                  !val || val === "all" ? "" : val
                );
              }}
            >
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Email Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                {emailStatusOptions.map((s) => (
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
                {stateOptions.map((s) => (
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
                  <SortableHeader label="Name" sortKey="lastName" currentSort={sort} onSort={handleSort} />
                  <SortableHeader label="Role" sortKey="role" currentSort={sort} onSort={handleSort} />
                  <SortableHeader label="District" sortKey="districtName" currentSort={sort} onSort={handleSort} />
                  <SortableHeader label="State" sortKey="state" currentSort={sort} onSort={handleSort} className="w-[60px]" />
                  <SortableHeader label="Email" sortKey="email" currentSort={sort} onSort={handleSort} />
                  <SortableHeader label="Status" sortKey="emailStatus" currentSort={sort} onSort={handleSort} />
                  <SortableHeader label="Phone" sortKey="phone" currentSort={sort} onSort={handleSort} />
                  <SortableHeader label="Confidence" sortKey="confidenceScore" currentSort={sort} onSort={handleSort} className="text-right" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedContacts.map((c) => (
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

        <Pagination
          page={filters.page ?? 1}
          totalPages={totalPages}
          total={total}
          pageSize={filters.pageSize ?? 20}
          onPageChange={(p) => setFilters((prev) => ({ ...prev, page: p }))}
          onPageSizeChange={(size) => setFilters((prev) => ({ ...prev, pageSize: size, page: 1 }))}
        />
      </Card>

      {/* Data Source Disclaimer */}
      <div className="rounded-lg border border-dashed p-4 text-xs text-muted-foreground">
        <p className="font-medium mb-1">Data Sources</p>
        <ul className="list-disc list-inside space-y-0.5">
          <li>Florida: <a href="https://www.fldoe.org/accountability/data-sys/school-dis-data/superintendents.stml" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">FL Department of Education</a></li>
          <li>California: <a href="https://www.cde.ca.gov/ds/si/ds/pubschls.asp" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">CA Department of Education (CDE)</a></li>
          <li>Texas: <a href="https://tea.texas.gov/texas-schools/general-information/school-district-locator" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">TX Education Agency (TEA)</a></li>
          <li>New York: <a href="https://www.p12.nysed.gov/ims/schoolDirectory/" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">NY State Education Department (NYSED)</a></li>
          <li>Illinois: <a href="https://www.isbe.net/Pages/Illinois-Directory-of-Educational-Entities.aspx" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">IL State Board of Education (ISBE)</a></li>
          <li>Massachusetts: <a href="https://profiles.doe.mass.edu/" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">MA Department of Elementary &amp; Secondary Education (DESE)</a></li>
          <li>Washington: <a href="https://eds.ospi.k12.wa.us/DirectoryEDS.aspx" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">WA Office of Superintendent of Public Instruction (OSPI)</a></li>
          <li>Oregon: <a href="https://www.oregon.gov/ode/" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">OR Department of Education (ODE)</a></li>
          <li>New Jersey: <a href="https://www.nj.gov/education/" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">NJ Department of Education</a></li>
        </ul>
        <p className="mt-1.5 text-[10px]">Contact data is sourced from publicly available state education department directories. Superintendent turnover is ~15–20% annually — data is verified periodically but may not reflect the most recent personnel changes.</p>
      </div>
    </div>
  );
}
