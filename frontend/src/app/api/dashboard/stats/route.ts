import { NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET() {
  try {
    const [
      districtsResult,
      eslResult,
      titleIResult,
      contactsResult,
      verifiedResult,
      campaignsResult,
    ] = await Promise.all([
      query("SELECT COUNT(*) as count FROM districts"),
      query("SELECT COUNT(*) as count FROM districts WHERE esl_program_status = true"),
      query("SELECT COUNT(*) as count FROM districts WHERE title_i_status = true"),
      query("SELECT COUNT(*) as count FROM contacts"),
      query("SELECT COUNT(*) as count FROM contacts WHERE email IS NOT NULL AND email != ''"),
      query("SELECT COUNT(*) as count FROM campaigns WHERE status = 'active'").catch(() => ({
        rows: [{ count: "0" }],
      })),
    ]);

    return NextResponse.json({
      totalDistricts: parseInt(districtsResult.rows[0].count, 10),
      districtsWithEsl: parseInt(eslResult.rows[0].count, 10),
      districtsWithTitleI: parseInt(titleIResult.rows[0].count, 10),
      totalContacts: parseInt(contactsResult.rows[0].count, 10),
      verifiedContacts: parseInt(verifiedResult.rows[0].count, 10),
      unverifiedContacts:
        parseInt(contactsResult.rows[0].count, 10) -
        parseInt(verifiedResult.rows[0].count, 10),
      activeCampaigns: parseInt(campaignsResult.rows[0].count, 10),
      emailsSentToday: 0,
      emailsSentThisWeek: 0,
    });
  } catch (error) {
    console.error("Dashboard stats API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch dashboard stats", detail: String(error) },
      { status: 500 }
    );
  }
}
