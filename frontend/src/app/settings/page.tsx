"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";

export default function SettingsPage() {
  // Mailgun
  const [mailgunDomain, setMailgunDomain] = useState("mg.yourdomain.com");
  const [mailgunApiKey, setMailgunApiKey] = useState("");
  const [mailgunFrom, setMailgunFrom] = useState("outreach@yourdomain.com");

  // Company
  const [companyName, setCompanyName] = useState("EduTech Solutions");
  const [companyAddress, setCompanyAddress] = useState(
    "123 Main St, Suite 400, Austin, TX 78701"
  );
  const [companyPhone, setCompanyPhone] = useState("(512) 555-0100");

  // Sending
  const [dailyLimit, setDailyLimit] = useState("50");
  const [hourlyLimit, setHourlyLimit] = useState("10");
  const [warmupEnabled, setWarmupEnabled] = useState(true);
  const [warmupStart, setWarmupStart] = useState("5");
  const [warmupIncrement, setWarmupIncrement] = useState("5");

  // Unsubscribe
  const [unsubscribeUrl, setUnsubscribeUrl] = useState(
    "https://yourdomain.com/unsubscribe"
  );

  function handleSave(section: string) {
    toast.success(`${section} settings saved`);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Configure your outreach system and email sending.
        </p>
      </div>

      <Tabs defaultValue="mailgun">
        <TabsList>
          <TabsTrigger value="mailgun">Mailgun</TabsTrigger>
          <TabsTrigger value="company">Company Info</TabsTrigger>
          <TabsTrigger value="sending">Sending Limits</TabsTrigger>
          <TabsTrigger value="compliance">Compliance</TabsTrigger>
        </TabsList>

        {/* Mailgun Configuration */}
        <TabsContent value="mailgun" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Mailgun Configuration
              </CardTitle>
              <CardDescription>
                Connect your Mailgun account for email sending and tracking.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Sending Domain
                </label>
                <Input
                  placeholder="mg.yourdomain.com"
                  value={mailgunDomain}
                  onChange={(e) => setMailgunDomain(e.target.value)}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  The verified domain in your Mailgun account.
                </p>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  API Key
                </label>
                <Input
                  type="password"
                  placeholder="key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                  value={mailgunApiKey}
                  onChange={(e) => setMailgunApiKey(e.target.value)}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Your Mailgun private API key. This will be stored securely.
                </p>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  From Address
                </label>
                <Input
                  placeholder="outreach@yourdomain.com"
                  value={mailgunFrom}
                  onChange={(e) => setMailgunFrom(e.target.value)}
                />
              </div>
              <Separator />
              <Button onClick={() => handleSave("Mailgun")}>
                Save Mailgun Settings
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Company Info */}
        <TabsContent value="company" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Company Information</CardTitle>
              <CardDescription>
                Required for CAN-SPAM compliance. This information appears in
                email footers.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Company Name
                </label>
                <Input
                  placeholder="Your Company Name"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Physical Address
                </label>
                <Input
                  placeholder="123 Main St, Suite 400, City, State ZIP"
                  value={companyAddress}
                  onChange={(e) => setCompanyAddress(e.target.value)}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  A valid physical postal address is required by CAN-SPAM.
                </p>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Phone Number
                </label>
                <Input
                  placeholder="(555) 555-0100"
                  value={companyPhone}
                  onChange={(e) => setCompanyPhone(e.target.value)}
                />
              </div>
              <Separator />
              <Button onClick={() => handleSave("Company")}>
                Save Company Info
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sending Limits */}
        <TabsContent value="sending" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Sending Limits</CardTitle>
              <CardDescription>
                Configure daily and hourly sending limits to protect your
                domain reputation.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Daily Limit
                  </label>
                  <Input
                    type="number"
                    placeholder="50"
                    value={dailyLimit}
                    onChange={(e) => setDailyLimit(e.target.value)}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Maximum emails sent per day.
                  </p>
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium">
                    Hourly Limit
                  </label>
                  <Input
                    type="number"
                    placeholder="10"
                    value={hourlyLimit}
                    onChange={(e) => setHourlyLimit(e.target.value)}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Maximum emails sent per hour.
                  </p>
                </div>
              </div>
              <Separator />
              <div>
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="warmup"
                    checked={warmupEnabled}
                    onChange={(e) => setWarmupEnabled(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <label htmlFor="warmup" className="text-sm font-medium">
                    Enable Email Warmup
                  </label>
                </div>
                <p className="ml-7 text-xs text-muted-foreground">
                  Gradually increase sending volume to build domain reputation.
                </p>
              </div>
              {warmupEnabled && (
                <div className="ml-7 grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">
                      Start Volume (per day)
                    </label>
                    <Input
                      type="number"
                      placeholder="5"
                      value={warmupStart}
                      onChange={(e) => setWarmupStart(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">
                      Daily Increment
                    </label>
                    <Input
                      type="number"
                      placeholder="5"
                      value={warmupIncrement}
                      onChange={(e) => setWarmupIncrement(e.target.value)}
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      Increase volume by this many each day.
                    </p>
                  </div>
                </div>
              )}
              <Separator />
              <Button onClick={() => handleSave("Sending limits")}>
                Save Sending Settings
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Compliance */}
        <TabsContent value="compliance" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Compliance & Unsubscribe
              </CardTitle>
              <CardDescription>
                Configure CAN-SPAM compliance settings.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium">
                  Unsubscribe Page URL
                </label>
                <Input
                  placeholder="https://yourdomain.com/unsubscribe"
                  value={unsubscribeUrl}
                  onChange={(e) => setUnsubscribeUrl(e.target.value)}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  This link will be included in all outgoing emails. CAN-SPAM
                  requires a working unsubscribe mechanism.
                </p>
              </div>
              <Separator />
              <div className="rounded-md border border-yellow-200 bg-yellow-50 p-4">
                <p className="text-sm font-medium text-yellow-800">
                  CAN-SPAM Requirements
                </p>
                <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-yellow-700">
                  <li>
                    Every email must include your physical postal address.
                  </li>
                  <li>
                    Every email must include a clear unsubscribe mechanism.
                  </li>
                  <li>
                    Unsubscribe requests must be honored within 10 business
                    days.
                  </li>
                  <li>
                    The &quot;From&quot; and &quot;Subject&quot; lines must be
                    accurate and not misleading.
                  </li>
                  <li>
                    The message must be identified as an advertisement if
                    applicable.
                  </li>
                </ul>
              </div>
              <Separator />
              <Button onClick={() => handleSave("Compliance")}>
                Save Compliance Settings
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
