"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
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
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ArrowLeft,
  Play,
  Pause,
  RotateCcw,
  Clock,
  Mail,
} from "lucide-react";
import { getCampaign, getCampaignAnalytics, updateCampaignStatus } from "@/lib/api";
import { CampaignDetail, CampaignAnalytics } from "@/types";
import { formatNumber, formatPercent, formatDate, formatDateTime } from "@/lib/format";
import { toast } from "sonner";

const statusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  draft: "secondary",
  paused: "outline",
  completed: "default",
};

const enrollmentStatusVariant: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  active: "default",
  completed: "secondary",
  replied: "default",
  bounced: "destructive",
  unsubscribed: "outline",
};

export default function CampaignDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [analytics, setAnalytics] = useState<CampaignAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const { sort: enrollmentSort, handleSort: handleEnrollmentSort, sortedData: sortedEnrollments } = useSort(campaign?.enrollments ?? []);
  const { sort: dailySort, handleSort: handleDailySort, sortedData: sortedDailyStats } = useSort(analytics?.dailyStats ?? []);

  useEffect(() => {
    async function load() {
      const [c, a] = await Promise.all([
        getCampaign(id),
        getCampaignAnalytics(id),
      ]);
      setCampaign(c);
      setAnalytics(a);
      setLoading(false);
    }
    load();
  }, [id]);

  async function handleStatusChange(newStatus: string) {
    if (!campaign) return;
    const updated = await updateCampaignStatus(id, newStatus);
    setCampaign((prev) => (prev ? { ...prev, status: updated.status } : prev));
    toast.success(`Campaign ${newStatus}`);
  }

  if (loading || !campaign || !analytics) {
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
          href="/campaigns"
          className={cn(buttonVariants({ variant: "ghost", size: "sm" }))}
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back
        </Link>
      </div>

      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{campaign.name}</h1>
            <Badge variant={statusVariant[campaign.status]}>
              {campaign.status}
            </Badge>
          </div>
          <p className="mt-1 text-muted-foreground">{campaign.description}</p>
        </div>
        <div className="flex gap-2">
          {campaign.status === "draft" && (
            <Button onClick={() => handleStatusChange("active")}>
              <Play className="mr-1 h-4 w-4" />
              Start
            </Button>
          )}
          {campaign.status === "active" && (
            <Button
              variant="outline"
              onClick={() => handleStatusChange("paused")}
            >
              <Pause className="mr-1 h-4 w-4" />
              Pause
            </Button>
          )}
          {campaign.status === "paused" && (
            <Button onClick={() => handleStatusChange("active")}>
              <RotateCcw className="mr-1 h-4 w-4" />
              Resume
            </Button>
          )}
        </div>
      </div>

      {/* Analytics Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {[
          { label: "Open Rate", value: analytics.openRate },
          { label: "Click Rate", value: analytics.clickRate },
          { label: "Reply Rate", value: analytics.replyRate },
          { label: "Bounce Rate", value: analytics.bounceRate },
          { label: "Unsubscribe", value: analytics.unsubscribeRate },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">{s.label}</p>
              <p className="mt-1 text-2xl font-bold">
                {formatPercent(s.value)}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Campaign Stats Row */}
      <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {[
          { label: "Enrolled", value: campaign.enrolled },
          { label: "Sent", value: campaign.sent },
          { label: "Opened", value: campaign.opened },
          { label: "Clicked", value: campaign.clicked },
          { label: "Replied", value: campaign.replied },
          { label: "Bounced", value: campaign.bounced },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="p-3 text-center">
              <p className="text-xs text-muted-foreground">{s.label}</p>
              <p className="mt-0.5 text-xl font-bold">
                {formatNumber(s.value)}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="sequence">
        <TabsList>
          <TabsTrigger value="sequence">Sequence</TabsTrigger>
          <TabsTrigger value="enrollments">
            Enrollments ({campaign.enrollments.length})
          </TabsTrigger>
          <TabsTrigger value="daily">Daily Stats</TabsTrigger>
        </TabsList>

        {/* Sequence Steps */}
        <TabsContent value="sequence" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Sequence Steps</CardTitle>
              <CardDescription>
                The email sequence that enrolled contacts go through.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {campaign.steps.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No steps configured yet.
                </p>
              ) : (
                campaign.steps.map((step, idx) => (
                  <div key={step.id}>
                    {idx > 0 && (
                      <div className="my-3 flex items-center gap-2 pl-4">
                        <Clock className="h-3 w-3 text-muted-foreground" />
                        <span className="text-xs text-muted-foreground">
                          Wait {step.delayDays} day{step.delayDays !== 1 ? "s" : ""}
                        </span>
                        <Separator className="flex-1" />
                      </div>
                    )}
                    <div className="flex items-start gap-4 rounded-lg border p-4">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">
                        {step.order}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <Mail className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm font-medium">
                            {step.templateName}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground">
                          Subject: {step.subject}
                        </p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Enrollments */}
        <TabsContent value="enrollments" className="mt-4">
          <Card>
            <CardContent className="p-0">
              {campaign.enrollments.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <p className="text-sm text-muted-foreground">
                    No contacts enrolled yet.
                  </p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <SortableHeader label="Contact" sortKey="contactName" currentSort={enrollmentSort} onSort={handleEnrollmentSort} />
                      <SortableHeader label="Email" sortKey="contactEmail" currentSort={enrollmentSort} onSort={handleEnrollmentSort} />
                      <SortableHeader label="District" sortKey="districtName" currentSort={enrollmentSort} onSort={handleEnrollmentSort} />
                      <SortableHeader label="Step" sortKey="currentStep" currentSort={enrollmentSort} onSort={handleEnrollmentSort} className="text-center" />
                      <SortableHeader label="Status" sortKey="status" currentSort={enrollmentSort} onSort={handleEnrollmentSort} />
                      <SortableHeader label="Enrolled" sortKey="enrolledAt" currentSort={enrollmentSort} onSort={handleEnrollmentSort} />
                      <SortableHeader label="Last Activity" sortKey="lastActivityAt" currentSort={enrollmentSort} onSort={handleEnrollmentSort} />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedEnrollments.map((e) => (
                      <TableRow key={e.id}>
                        <TableCell className="font-medium">
                          {e.contactName}
                        </TableCell>
                        <TableCell className="text-sm">
                          {e.contactEmail}
                        </TableCell>
                        <TableCell className="text-sm">
                          {e.districtName}
                        </TableCell>
                        <TableCell className="text-center">
                          {e.currentStep} / {campaign.steps.length}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              enrollmentStatusVariant[e.status] ?? "outline"
                            }
                          >
                            {e.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">
                          {formatDate(e.enrolledAt)}
                        </TableCell>
                        <TableCell className="text-sm">
                          {formatDateTime(e.lastActivityAt)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Daily Stats */}
        <TabsContent value="daily" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Daily Sending Stats</CardTitle>
              <CardDescription>
                Email activity over the past 7 days.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <SortableHeader label="Date" sortKey="date" currentSort={dailySort} onSort={handleDailySort} />
                    <SortableHeader label="Sent" sortKey="sent" currentSort={dailySort} onSort={handleDailySort} className="text-right" />
                    <SortableHeader label="Opened" sortKey="opened" currentSort={dailySort} onSort={handleDailySort} className="text-right" />
                    <SortableHeader label="Clicked" sortKey="clicked" currentSort={dailySort} onSort={handleDailySort} className="text-right" />
                    <SortableHeader label="Replied" sortKey="replied" currentSort={dailySort} onSort={handleDailySort} className="text-right" />
                    <TableHead className="text-right">Open Rate</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedDailyStats.map((day) => (
                    <TableRow key={day.date}>
                      <TableCell className="font-medium">
                        {formatDate(day.date + "T00:00:00Z")}
                      </TableCell>
                      <TableCell className="text-right">
                        {day.sent}
                      </TableCell>
                      <TableCell className="text-right">
                        {day.opened}
                      </TableCell>
                      <TableCell className="text-right">
                        {day.clicked}
                      </TableCell>
                      <TableCell className="text-right">
                        {day.replied}
                      </TableCell>
                      <TableCell className="text-right">
                        {day.sent > 0
                          ? formatPercent((day.opened / day.sent) * 100)
                          : "-"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
