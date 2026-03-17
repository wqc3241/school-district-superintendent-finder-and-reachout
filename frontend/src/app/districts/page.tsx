"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
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
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { getDistricts } from "@/lib/api";
import { District, DistrictFilters } from "@/types";
import { formatNumber, formatCurrency, formatPercent } from "@/lib/format";

export default function DistrictsPage() {
  const [districts, setDistricts] = useState<District[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [stateOptions, setStateOptions] = useState<string[]>([]);
  const [filters, setFilters] = useState<DistrictFilters>({
    search: "",
    state: "",
    hasEslProgram: null,
    fundingType: "",
    page: 1,
    pageSize: 20,
  });

  const { sort, handleSort, sortedData: sortedDistricts } = useSort(districts);

  useEffect(() => {
    fetch("/api/states?from=districts").then(r => r.json()).then(setStateOptions).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    const cleanFilters: DistrictFilters = { ...filters };
    if (!cleanFilters.search) delete cleanFilters.search;
    if (!cleanFilters.state) delete cleanFilters.state;
    if (cleanFilters.hasEslProgram === null) delete cleanFilters.hasEslProgram;
    const res = await getDistricts(cleanFilters);
    setDistricts(res.data);
    setTotal(res.total);
    setTotalPages(res.totalPages);
    setLoading(false);
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  function updateFilter<K extends keyof DistrictFilters>(
    key: K,
    value: DistrictFilters[K]
  ) {
    setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Districts</h1>
        <p className="text-muted-foreground">
          Browse and filter school districts with ELL programs.
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search districts, superintendents, cities..."
                value={filters.search ?? ""}
                onChange={(e) => updateFilter("search", e.target.value)}
                className="pl-9"
              />
            </div>
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
            <Select
              value={
                filters.hasEslProgram === null
                  ? "all"
                  : filters.hasEslProgram
                    ? "yes"
                    : "no"
              }
              onValueChange={(v) => {
                const val = v as string | null;
                updateFilter(
                  "hasEslProgram",
                  !val || val === "all" ? null : val === "yes"
                );
              }}
            >
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="ESL Program" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Programs</SelectItem>
                <SelectItem value="yes">Has ESL</SelectItem>
                <SelectItem value="no">No ESL</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={filters.fundingType ?? ""}
              onValueChange={(v) => {
                const val = v as string | null;
                updateFilter(
                  "fundingType",
                  !val || val === "all" ? "" : val as "title_i" | "title_iii" | "both"
                );
              }}
            >
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Funding Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Funding</SelectItem>
                <SelectItem value="title_i">Title I</SelectItem>
                <SelectItem value="title_iii">Title III</SelectItem>
                <SelectItem value="both">Title I & III</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                setFilters({
                  search: "",
                  state: "",
                  hasEslProgram: null,
                  fundingType: "",
                  page: 1,
                  pageSize: 20,
                })
              }
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
            {formatNumber(total)} Districts
          </CardTitle>
          <CardDescription>
            Click a row to view district details and contacts.
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
          ) : districts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-muted-foreground">
                No districts match your filters.
              </p>
              <Button
                variant="link"
                onClick={() =>
                  setFilters({
                    search: "",
                    state: "",
                    hasEslProgram: null,
                    fundingType: "",
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
                  <SortableHeader label="Name" sortKey="name" currentSort={sort} onSort={handleSort} />
                  <SortableHeader label="State" sortKey="state" currentSort={sort} onSort={handleSort} className="w-[60px]" />
                  <SortableHeader label="City" sortKey="city" currentSort={sort} onSort={handleSort} />
                  <SortableHeader label="ELL Students" sortKey="ellStudents" currentSort={sort} onSort={handleSort} className="text-right" />
                  <SortableHeader label="ELL %" sortKey="ellPercentage" currentSort={sort} onSort={handleSort} className="text-right" />
                  <SortableHeader label="Title I" sortKey="titleIFunding" currentSort={sort} onSort={handleSort} className="text-right" />
                  <SortableHeader label="Title III" sortKey="titleIIIFunding" currentSort={sort} onSort={handleSort} className="text-right" />
                  <SortableHeader label="Funding" sortKey="hasTitleI" currentSort={sort} onSort={handleSort} className="w-[120px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedDistricts.map((d) => (
                  <TableRow key={d.id} className="cursor-pointer">
                    <TableCell>
                      <Link
                        href={`/districts/${d.id}`}
                        className="font-medium hover:underline"
                      >
                        {d.name}
                      </Link>
                    </TableCell>
                    <TableCell>{d.state}</TableCell>
                    <TableCell className="text-muted-foreground">{d.city}</TableCell>
                    <TableCell className="text-right">
                      {formatNumber(d.ellStudents || null)}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatPercent(d.ellPercentage || null)}
                    </TableCell>
                    <TableCell className="text-right">
                      {d.titleIFunding ? formatCurrency(d.titleIFunding) : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      {d.titleIIIFunding ? formatCurrency(d.titleIIIFunding) : "—"}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {d.hasTitleI && (
                          <Badge variant="default" className="text-[10px] px-1.5 py-0">I</Badge>
                        )}
                        {d.hasEslProgram && (
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">III</Badge>
                        )}
                        {!d.hasTitleI && !d.hasEslProgram && (
                          <span className="text-muted-foreground text-xs">—</span>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>

        {/* Pagination */}
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

      {/* Data Source Disclaimer */}
      <div className="rounded-lg border border-dashed p-4 text-xs text-muted-foreground">
        <p className="font-medium mb-1">Data Sources</p>
        <ul className="list-disc list-inside space-y-0.5">
          <li>District data: <a href="https://nces.ed.gov/ccd/" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">NCES Common Core of Data (CCD)</a> — U.S. Department of Education</li>
          <li>ELL student counts: <a href="https://educationdata.urban.org/" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">Urban Institute Education Data Portal</a></li>
          <li>Title I funding: <a href="https://www.ed.gov/grants-and-programs/formula-grants" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">U.S. Department of Education Formula Grants</a></li>
          <li>Title III funding: <a href="https://ncela.ed.gov/title-iii-state-formula-grants" target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">National Clearinghouse for English Language Acquisition (NCELA)</a></li>
        </ul>
        <p className="mt-1.5 text-[10px]">Data may be 1–2 years behind current school year. District counts and funding amounts are based on the most recent federal reporting cycle available.</p>
      </div>
    </div>
  );
}
