import {
  PaginatedResponse,
  District,
  DistrictFilters,
  Contact,
  ContactFilters,
  Campaign,
  CampaignDetail,
  CreateCampaign,
  EmailTemplate,
  CreateTemplate,
  DashboardStats,
  CampaignAnalytics,
  ActivityItem,
} from "@/types";
import {
  mockCampaigns,
  mockCampaignDetail,
  mockTemplates,
  mockCampaignAnalytics,
} from "./mock-data";

// ── Generic fetch helper (relative URLs — works on localhost and Vercel) ──
async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API error: ${res.status} ${res.statusText} — ${body}`);
  }
  return res.json();
}

// ── Districts ────────────────────────────────────────────────────────
export async function getDistricts(
  params: DistrictFilters = {}
): Promise<PaginatedResponse<District>> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("size", String(params.pageSize));
  if (params.state) query.set("state", params.state);
  if (params.search) query.set("query", params.search);
  if (params.hasEslProgram === true) query.set("esl_only", "true");
  if (params.fundingType) query.set("funding_type", params.fundingType);
  if (params.sortKey) query.set("sort_key", params.sortKey);
  if (params.sortDir) query.set("sort_dir", params.sortDir);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw = await apiFetch<{ items: any[]; total: number; page: number; size: number }>(
    `/api/districts?${query.toString()}`
  );

  const mapped: District[] = raw.items.map((d) => ({
    id: d.id,
    name: d.name,
    state: d.state,
    city: d.city || "",
    address: d.address || "",
    phone: d.phone || "",
    website: d.website || "",
    totalStudents: 0,
    ellStudents: d.ell_student_count || 0,
    ellPercentage: parseFloat(d.ell_percentage) || 0,
    hasEslProgram: d.esl_program_status || false,
    titleIFunding: parseFloat(d.title_i_allocation) || 0,
    hasTitleI: d.title_i_status || false,
    titleIIIFunding: parseFloat(d.title_iii_allocation) || 0,
    superintendent: "",
    superintendentEmail: "",
    status: "active" as const,
    createdAt: d.created_at,
    updatedAt: d.updated_at,
  }));

  return {
    data: mapped,
    total: raw.total,
    page: raw.page,
    pageSize: raw.size,
    totalPages: Math.ceil(raw.total / raw.size),
  };
}

export async function getDistrict(id: string): Promise<District> {
  // Single district endpoint not yet implemented — fetch page and find
  const result = await getDistricts({ page: 1, pageSize: 1, search: id });
  if (result.data.length === 0) throw new Error("District not found");
  return result.data[0];
}

// ── Contacts ─────────────────────────────────────────────────────────
export async function getContacts(
  params: ContactFilters = {}
): Promise<PaginatedResponse<Contact>> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("size", String(params.pageSize));
  if (params.state) query.set("state", params.state);
  if (params.search) query.set("query", params.search);
  if (params.role) query.set("role", params.role);
  if (params.emailStatus) query.set("email_status", params.emailStatus);
  if (params.sortKey) query.set("sort_key", params.sortKey);
  if (params.sortDir) query.set("sort_dir", params.sortDir);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw = await apiFetch<{ items: any[]; total: number; page: number; size: number }>(
    `/api/contacts?${query.toString()}`
  );

  const mapped: Contact[] = raw.items.map((c) => ({
    id: c.id,
    firstName: c.first_name,
    lastName: c.last_name,
    role: c.role || "Superintendent",
    districtId: c.district_id,
    districtName: c.district_name || "",
    state: c.state || "",
    email: c.email || "",
    emailStatus: c.email_status || "unverified",
    phone: c.phone || "",
    confidenceScore: c.confidence_score || 0,
    linkedinUrl: "",
    createdAt: c.created_at,
    updatedAt: c.updated_at,
  }));

  return {
    data: mapped,
    total: raw.total,
    page: raw.page,
    pageSize: raw.size,
    totalPages: Math.ceil(raw.total / raw.size),
  };
}

export async function getContact(id: string): Promise<Contact> {
  const result = await getContacts({ page: 1, pageSize: 1, search: id });
  if (result.data.length === 0) throw new Error("Contact not found");
  return result.data[0];
}

// ── Campaigns (mock data — not in DB yet) ────────────────────────────
export async function getCampaigns(): Promise<Campaign[]> {
  return mockCampaigns;
}

export async function getCampaign(id: string): Promise<CampaignDetail> {
  const c = mockCampaigns.find((c) => c.id === id);
  if (!c) throw new Error("Campaign not found");
  if (c.id === mockCampaignDetail.id) return mockCampaignDetail;
  return {
    ...c,
    steps: mockCampaignDetail.steps,
    enrollments: mockCampaignDetail.enrollments.slice(0, 3),
  };
}

export async function createCampaign(
  data: CreateCampaign
): Promise<Campaign> {
  return {
    id: `camp${Date.now()}`,
    ...data,
    status: "draft",
    enrolled: 0,
    sent: 0,
    opened: 0,
    clicked: 0,
    replied: 0,
    bounced: 0,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

export async function updateCampaignStatus(
  id: string,
  status: string
): Promise<Campaign> {
  const c = mockCampaigns.find((c) => c.id === id);
  if (!c) throw new Error("Campaign not found");
  return { ...c, status: status as Campaign["status"] };
}

// ── Templates (mock data — not in DB yet) ────────────────────────────
export async function getTemplates(): Promise<EmailTemplate[]> {
  return mockTemplates;
}

export async function getTemplate(id: string): Promise<EmailTemplate> {
  const t = mockTemplates.find((t) => t.id === id);
  if (!t) throw new Error("Template not found");
  return t;
}

export async function createTemplate(
  data: CreateTemplate
): Promise<EmailTemplate> {
  return {
    id: `t${Date.now()}`,
    ...data,
    variables: extractVariables(data.body),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

export async function updateTemplate(
  id: string,
  data: CreateTemplate
): Promise<EmailTemplate> {
  const t = mockTemplates.find((t) => t.id === id);
  if (!t) throw new Error("Template not found");
  return {
    ...t,
    ...data,
    variables: extractVariables(data.body),
    updatedAt: new Date().toISOString(),
  };
}

// ── Analytics / Dashboard ────────────────────────────────────────────
export async function getDashboardStats(): Promise<DashboardStats> {
  return apiFetch<DashboardStats>("/api/dashboard/stats");
}

export async function getCampaignAnalytics(
  id: string
): Promise<CampaignAnalytics> {
  // Campaign analytics not in DB yet — use mock
  return { ...mockCampaignAnalytics, campaignId: id };
}

export async function getActivityFeed(): Promise<ActivityItem[]> {
  return apiFetch<ActivityItem[]>("/api/dashboard/activity");
}

// ── Utilities ────────────────────────────────────────────────────────
function extractVariables(text: string): string[] {
  const matches = text.match(/\{\{([^}]+)\}\}/g);
  if (!matches) return [];
  return [...new Set(matches.map((m) => m.replace(/[{}]/g, "").trim()))];
}
