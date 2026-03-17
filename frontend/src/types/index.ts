// ── Shared / Pagination ──────────────────────────────────────────────
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// ── District ─────────────────────────────────────────────────────────
export interface District {
  id: string;
  name: string;
  state: string;
  city: string;
  address: string;
  phone: string;
  website: string;
  totalStudents: number;
  ellStudents: number;
  ellPercentage: number;
  hasEslProgram: boolean;
  titleIFunding: number;
  hasTitleI: boolean;
  titleIIIFunding: number;
  superintendent: string;
  superintendentEmail: string;
  status: "active" | "inactive" | "pending";
  createdAt: string;
  updatedAt: string;
}

export interface DistrictFilters {
  search?: string;
  state?: string;
  hasEslProgram?: boolean | null;
  fundingType?: "title_i" | "title_iii" | "both" | "";
  ellStudentsMin?: number;
  ellStudentsMax?: number;
  page?: number;
  pageSize?: number;
}

// ── Contact ──────────────────────────────────────────────────────────

export interface Contact {
  id: string;
  firstName: string;
  lastName: string;
  role: string;
  districtId: string;
  districtName: string;
  state: string;
  email: string;
  emailStatus: string;
  phone: string;
  confidenceScore: number;
  linkedinUrl: string;
  createdAt: string;
  updatedAt: string;
}

export interface ContactFilters {
  search?: string;
  role?: string;
  emailStatus?: string;
  state?: string;
  confidenceScoreMin?: number;
  confidenceScoreMax?: number;
  districtId?: string;
  page?: number;
  pageSize?: number;
}

// ── Campaign ─────────────────────────────────────────────────────────
export type CampaignStatus = "draft" | "active" | "paused" | "completed";

export interface Campaign {
  id: string;
  name: string;
  description: string;
  status: CampaignStatus;
  enrolled: number;
  sent: number;
  opened: number;
  clicked: number;
  replied: number;
  bounced: number;
  createdAt: string;
  updatedAt: string;
}

export interface SequenceStep {
  id: string;
  order: number;
  delayDays: number;
  templateId: string;
  templateName: string;
  subject: string;
}

export interface Enrollment {
  id: string;
  contactId: string;
  contactName: string;
  contactEmail: string;
  districtName: string;
  currentStep: number;
  status: "active" | "completed" | "replied" | "bounced" | "unsubscribed";
  enrolledAt: string;
  lastActivityAt: string;
}

export interface CampaignDetail extends Campaign {
  steps: SequenceStep[];
  enrollments: Enrollment[];
}

export interface CreateCampaign {
  name: string;
  description: string;
}

// ── Email Template ───────────────────────────────────────────────────
export interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body: string;
  variables: string[];
  createdAt: string;
  updatedAt: string;
}

export interface CreateTemplate {
  name: string;
  subject: string;
  body: string;
}

// ── Dashboard / Analytics ────────────────────────────────────────────
export interface DashboardStats {
  totalDistricts: number;
  districtsWithEsl: number;
  districtsWithTitleI: number;
  totalContacts: number;
  verifiedContacts: number;
  unverifiedContacts: number;
  activeCampaigns: number;
  emailsSentToday: number;
  emailsSentThisWeek: number;
}

export interface CampaignAnalytics {
  campaignId: string;
  openRate: number;
  clickRate: number;
  replyRate: number;
  bounceRate: number;
  unsubscribeRate: number;
  dailyStats: {
    date: string;
    sent: number;
    opened: number;
    clicked: number;
    replied: number;
  }[];
}

export interface ActivityItem {
  id: string;
  type: "email_sent" | "email_opened" | "reply_received" | "contact_added" | "campaign_started" | "bounce";
  description: string;
  timestamp: string;
}
