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
import { Separator } from "@/components/ui/separator";
import {
  Building2,
  Users,
  Send,
  Mail,
  CheckCircle,
  AlertCircle,
  MessageSquare,
  UserPlus,
  Rocket,
  XCircle,
} from "lucide-react";
import { getDashboardStats, getActivityFeed } from "@/lib/api";
import { DashboardStats, ActivityItem } from "@/types";
import { formatNumber, timeAgo } from "@/lib/format";

const activityIcons: Record<ActivityItem["type"], React.ReactNode> = {
  email_sent: <Mail className="h-4 w-4 text-blue-500" />,
  email_opened: <CheckCircle className="h-4 w-4 text-green-500" />,
  reply_received: <MessageSquare className="h-4 w-4 text-purple-500" />,
  contact_added: <UserPlus className="h-4 w-4 text-cyan-500" />,
  campaign_started: <Rocket className="h-4 w-4 text-orange-500" />,
  bounce: <XCircle className="h-4 w-4 text-red-500" />,
};

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [s, a] = await Promise.all([
        getDashboardStats(),
        getActivityFeed(),
      ]);
      setStats(s);
      setActivity(a);
      setLoading(false);
    }
    load();
  }, []);

  if (loading || !stats) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="h-16 animate-pulse rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const statCards = [
    {
      title: "Total Districts",
      value: formatNumber(stats.totalDistricts),
      sub: `${formatNumber(stats.districtsWithEsl)} with ESL programs`,
      icon: Building2,
      color: "text-blue-600",
    },
    {
      title: "Total Contacts",
      value: formatNumber(stats.totalContacts),
      sub: `${formatNumber(stats.verifiedContacts)} verified / ${formatNumber(stats.unverifiedContacts)} unverified`,
      icon: Users,
      color: "text-green-600",
    },
    {
      title: "Active Campaigns",
      value: String(stats.activeCampaigns),
      sub: "Currently running",
      icon: Send,
      color: "text-purple-600",
    },
    {
      title: "Emails Sent",
      value: formatNumber(stats.emailsSentToday),
      sub: `${formatNumber(stats.emailsSentThisWeek)} this week`,
      icon: Mail,
      color: "text-orange-600",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your superintendent outreach program.
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <Card key={card.title}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-muted-foreground">
                  {card.title}
                </p>
                <card.icon className={`h-5 w-5 ${card.color}`} />
              </div>
              <p className="mt-2 text-3xl font-bold">{card.value}</p>
              <p className="mt-1 text-xs text-muted-foreground">{card.sub}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Stats Row */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Verification Breakdown */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Email Verification</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-green-500" />
                <span className="text-sm">Verified</span>
              </div>
              <span className="text-sm font-medium">
                {formatNumber(stats.verifiedContacts)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-yellow-500" />
                <span className="text-sm">Unverified</span>
              </div>
              <span className="text-sm font-medium">
                {formatNumber(stats.unverifiedContacts)}
              </span>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Verification Rate
              </span>
              <span className="text-sm font-medium">
                {((stats.verifiedContacts / stats.totalContacts) * 100).toFixed(1)}%
              </span>
            </div>
          </CardContent>
        </Card>

        {/* ESL Coverage */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">ESL Program Coverage</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-sm">With ESL</span>
              </div>
              <span className="text-sm font-medium">
                {formatNumber(stats.districtsWithEsl)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm">Without ESL</span>
              </div>
              <span className="text-sm font-medium">
                {formatNumber(stats.totalDistricts - stats.districtsWithEsl)}
              </span>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Coverage</span>
              <span className="text-sm font-medium">
                {((stats.districtsWithEsl / stats.totalDistricts) * 100).toFixed(1)}%
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Sending Summary */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Sending Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm">Today</span>
              <Badge variant="secondary">
                {formatNumber(stats.emailsSentToday)} sent
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm">This Week</span>
              <Badge variant="secondary">
                {formatNumber(stats.emailsSentThisWeek)} sent
              </Badge>
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Daily Average</span>
              <span className="text-sm font-medium">
                {Math.round(stats.emailsSentThisWeek / 7)} / day
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Activity Feed */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Latest events across your campaigns.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {activity.map((item) => (
              <div key={item.id} className="flex items-start gap-3">
                <div className="mt-0.5">{activityIcons[item.type]}</div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm">{item.description}</p>
                  <p className="text-xs text-muted-foreground">
                    {timeAgo(item.timestamp)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
