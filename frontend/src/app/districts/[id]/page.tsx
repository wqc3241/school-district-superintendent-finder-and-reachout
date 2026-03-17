"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
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
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  Globe,
  Phone,
  MapPin,
  ExternalLink,
  Users,
  GraduationCap,
} from "lucide-react";
import { getDistrict, getContacts } from "@/lib/api";
import { District, Contact } from "@/types";
import { formatNumber, formatCurrency, formatPercent } from "@/lib/format";

const emailStatusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  verified: "default",
  unverified: "secondary",
  bounced: "destructive",
  catch_all: "outline",
  unknown: "outline",
};

export default function DistrictDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [district, setDistrict] = useState<District | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [d, c] = await Promise.all([
        getDistrict(id),
        getContacts({ districtId: id }),
      ]);
      setDistrict(d);
      setContacts(c.data);
      setLoading(false);
    }
    load();
  }, [id]);

  if (loading || !district) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted" />
        <div className="h-64 animate-pulse rounded bg-muted" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/districts"
          className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back
        </Link>
      </div>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{district.name}</h1>
          <p className="text-muted-foreground">
            {district.city}, {district.state}
          </p>
        </div>
        <Badge
          variant={
            district.status === "active"
              ? "default"
              : district.status === "pending"
                ? "secondary"
                : "outline"
          }
        >
          {district.status}
        </Badge>
      </div>

      {/* Info Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* District Info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">District Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3">
              <MapPin className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Address</p>
                <p className="text-sm text-muted-foreground">
                  {district.address}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Phone className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Phone</p>
                <p className="text-sm text-muted-foreground">
                  {district.phone}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Globe className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Website</p>
                <a
                  href={district.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-sm text-blue-600 hover:underline"
                >
                  {district.website}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
            <Separator />
            <div className="flex items-start gap-3">
              <Users className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Superintendent</p>
                <p className="text-sm text-muted-foreground">
                  {district.superintendent}
                </p>
                <p className="text-sm text-muted-foreground">
                  {district.superintendentEmail}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ESL Data */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">ESL / ELL Data</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Total Students</p>
                <p className="text-2xl font-bold">
                  {formatNumber(district.totalStudents)}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">ELL Students</p>
                <p className="text-2xl font-bold">
                  {formatNumber(district.ellStudents)}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">ELL Percentage</p>
                <p className="text-2xl font-bold">
                  {formatPercent(district.ellPercentage)}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Title III Funding
                </p>
                <p className="text-2xl font-bold">
                  {formatCurrency(district.titleIIIFunding)}
                </p>
              </div>
            </div>
            <Separator />
            <div className="flex items-center gap-3">
              <GraduationCap className="h-4 w-4 text-muted-foreground" />
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">ESL Program</span>
                {district.hasEslProgram ? (
                  <Badge>Active</Badge>
                ) : (
                  <Badge variant="outline">None</Badge>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Contacts Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Contacts ({contacts.length})
          </CardTitle>
          <CardDescription>
            People associated with this district.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {contacts.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <p className="text-sm text-muted-foreground">
                No contacts found for this district.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Email Status</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead className="text-right">Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {contacts.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium">
                      {c.firstName} {c.lastName}
                    </TableCell>
                    <TableCell>{c.role}</TableCell>
                    <TableCell className="text-sm">{c.email}</TableCell>
                    <TableCell>
                      <Badge variant={emailStatusVariant[c.emailStatus] ?? "outline"}>
                        {c.emailStatus}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{c.phone}</TableCell>
                    <TableCell className="text-right">
                      <span
                        className={
                          c.confidenceScore >= 80
                            ? "text-green-600 font-medium"
                            : c.confidenceScore >= 50
                              ? "text-yellow-600 font-medium"
                              : "text-red-600 font-medium"
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
      </Card>
    </div>
  );
}
