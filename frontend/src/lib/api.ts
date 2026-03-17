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
  mockDistricts,
  mockContacts,
  mockCampaigns,
  mockCampaignDetail,
  mockTemplates,
  mockDashboardStats,
  mockCampaignAnalytics,
  mockActivityFeed,
} from "./mock-data";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Generic fetch helper ─────────────────────────────────────────────
async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

// ── Helper: paginate an array locally (for mock data) ────────────────
function paginate<T>(
  items: T[],
  page: number = 1,
  pageSize: number = 20
): PaginatedResponse<T> {
  const total = items.length;
  const totalPages = Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize;
  return {
    data: items.slice(start, start + pageSize),
    total,
    page,
    pageSize,
    totalPages,
  };
}

// When the real API is available, set USE_MOCK to false or set NEXT_PUBLIC_API_URL.
const USE_MOCK = !process.env.NEXT_PUBLIC_API_URL;

// ── Districts ────────────────────────────────────────────────────────
export async function getDistricts(
  params: DistrictFilters = {}
): Promise<PaginatedResponse<District>> {
  if (USE_MOCK) {
    let filtered = [...mockDistricts];
    if (params.search) {
      const q = params.search.toLowerCase();
      filtered = filtered.filter(
        (d) =>
          d.name.toLowerCase().includes(q) ||
          d.superintendent.toLowerCase().includes(q) ||
          d.city.toLowerCase().includes(q)
      );
    }
    if (params.state) {
      filtered = filtered.filter((d) => d.state === params.state);
    }
    if (params.hasEslProgram !== undefined && params.hasEslProgram !== null) {
      filtered = filtered.filter((d) => d.hasEslProgram === params.hasEslProgram);
    }
    if (params.ellStudentsMin !== undefined) {
      filtered = filtered.filter((d) => d.ellStudents >= params.ellStudentsMin!);
    }
    if (params.ellStudentsMax !== undefined) {
      filtered = filtered.filter((d) => d.ellStudents <= params.ellStudentsMax!);
    }
    return paginate(filtered, params.page, params.pageSize);
  }
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("size", String(params.pageSize));
  if (params.state) query.set("state", params.state);
  if (params.search) query.set("query", params.search);
  if (params.hasEslProgram === true) query.set("esl_only", "true");
  if (params.fundingType) query.set("funding_type", params.fundingType);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw = await apiFetch<{ items: any[]; total: number; page: number; size: number }>(
    `/districts/?${query.toString()}`
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
    ellPercentage: d.ell_percentage || 0,
    hasEslProgram: d.esl_program_status || false,
    titleIFunding: d.title_i_allocation || 0,
    hasTitleI: d.title_i_status || false,
    titleIIIFunding: d.title_iii_allocation || 0,
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
  if (USE_MOCK) {
    const d = mockDistricts.find((d) => d.id === id);
    if (!d) throw new Error("District not found");
    return d;
  }
  return apiFetch<District>(`/districts/${id}`);
}

// ── Contacts ─────────────────────────────────────────────────────────
export async function getContacts(
  params: ContactFilters = {}
): Promise<PaginatedResponse<Contact>> {
  if (USE_MOCK) {
    let filtered = [...mockContacts];
    if (params.search) {
      const q = params.search.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          c.firstName.toLowerCase().includes(q) ||
          c.lastName.toLowerCase().includes(q) ||
          c.email.toLowerCase().includes(q) ||
          c.districtName.toLowerCase().includes(q)
      );
    }
    if (params.role) {
      filtered = filtered.filter((c) => c.role === params.role);
    }
    if (params.emailStatus) {
      filtered = filtered.filter((c) => c.emailStatus === params.emailStatus);
    }
    if (params.state) {
      filtered = filtered.filter((c) => c.state === params.state);
    }
    if (params.confidenceScoreMin !== undefined) {
      filtered = filtered.filter(
        (c) => c.confidenceScore >= params.confidenceScoreMin!
      );
    }
    if (params.confidenceScoreMax !== undefined) {
      filtered = filtered.filter(
        (c) => c.confidenceScore <= params.confidenceScoreMax!
      );
    }
    if (params.districtId) {
      filtered = filtered.filter((c) => c.districtId === params.districtId);
    }
    return paginate(filtered, params.page, params.pageSize);
  }
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("size", String(params.pageSize));
  if (params.state) query.set("state", params.state);
  if (params.search) query.set("query", params.search);
  if (params.role) query.set("role", params.role);
  if (params.emailStatus) query.set("email_status", params.emailStatus);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const raw = await apiFetch<{ items: any[]; total: number; page: number; size: number }>(
    `/contacts/?${query.toString()}`
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
  if (USE_MOCK) {
    const c = mockContacts.find((c) => c.id === id);
    if (!c) throw new Error("Contact not found");
    return c;
  }
  return apiFetch<Contact>(`/contacts/${id}`);
}

// ── Campaigns ────────────────────────────────────────────────────────
export async function getCampaigns(): Promise<Campaign[]> {
  if (USE_MOCK) return mockCampaigns;
  return apiFetch<Campaign[]>("/api/campaigns");
}

export async function getCampaign(id: string): Promise<CampaignDetail> {
  if (USE_MOCK) {
    const c = mockCampaigns.find((c) => c.id === id);
    if (!c) throw new Error("Campaign not found");
    if (c.id === mockCampaignDetail.id) return mockCampaignDetail;
    return {
      ...c,
      steps: mockCampaignDetail.steps,
      enrollments: mockCampaignDetail.enrollments.slice(0, 3),
    };
  }
  return apiFetch<CampaignDetail>(`/api/campaigns/${id}`);
}

export async function createCampaign(
  data: CreateCampaign
): Promise<Campaign> {
  if (USE_MOCK) {
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
  return apiFetch<Campaign>("/api/campaigns", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCampaignStatus(
  id: string,
  status: string
): Promise<Campaign> {
  if (USE_MOCK) {
    const c = mockCampaigns.find((c) => c.id === id);
    if (!c) throw new Error("Campaign not found");
    return { ...c, status: status as Campaign["status"] };
  }
  return apiFetch<Campaign>(`/api/campaigns/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

// ── Templates ────────────────────────────────────────────────────────
export async function getTemplates(): Promise<EmailTemplate[]> {
  if (USE_MOCK) return mockTemplates;
  return apiFetch<EmailTemplate[]>("/api/templates");
}

export async function getTemplate(id: string): Promise<EmailTemplate> {
  if (USE_MOCK) {
    const t = mockTemplates.find((t) => t.id === id);
    if (!t) throw new Error("Template not found");
    return t;
  }
  return apiFetch<EmailTemplate>(`/api/templates/${id}`);
}

export async function createTemplate(
  data: CreateTemplate
): Promise<EmailTemplate> {
  if (USE_MOCK) {
    return {
      id: `t${Date.now()}`,
      ...data,
      variables: extractVariables(data.body),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  }
  return apiFetch<EmailTemplate>("/api/templates", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTemplate(
  id: string,
  data: CreateTemplate
): Promise<EmailTemplate> {
  if (USE_MOCK) {
    const t = mockTemplates.find((t) => t.id === id);
    if (!t) throw new Error("Template not found");
    return {
      ...t,
      ...data,
      variables: extractVariables(data.body),
      updatedAt: new Date().toISOString(),
    };
  }
  return apiFetch<EmailTemplate>(`/api/templates/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// ── Analytics / Dashboard ────────────────────────────────────────────
export async function getDashboardStats(): Promise<DashboardStats> {
  if (USE_MOCK) return mockDashboardStats;
  try {
    return await apiFetch<DashboardStats>("/dashboard/stats");
  } catch {
    return mockDashboardStats;
  }
}

export async function getCampaignAnalytics(
  id: string
): Promise<CampaignAnalytics> {
  if (USE_MOCK) return { ...mockCampaignAnalytics, campaignId: id };
  try {
    return await apiFetch<CampaignAnalytics>(`/campaigns/${id}/analytics`);
  } catch {
    return { ...mockCampaignAnalytics, campaignId: id };
  }
}

export async function getActivityFeed(): Promise<ActivityItem[]> {
  if (USE_MOCK) return mockActivityFeed;
  try {
    return await apiFetch<ActivityItem[]>("/dashboard/activity");
  } catch {
    return mockActivityFeed;
  }
}

// ── Utilities ────────────────────────────────────────────────────────
function extractVariables(text: string): string[] {
  const matches = text.match(/\{\{([^}]+)\}\}/g);
  if (!matches) return [];
  return [...new Set(matches.map((m) => m.replace(/[{}]/g, "").trim()))];
}
