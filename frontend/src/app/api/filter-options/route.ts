import { NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET() {
  try {
    const [statesRes, rolesRes, statusRes] = await Promise.all([
      query(`SELECT DISTINCT d.state FROM contacts c JOIN districts d ON c.district_id = d.id WHERE d.state IS NOT NULL ORDER BY d.state`),
      query(`SELECT DISTINCT role FROM contacts WHERE role IS NOT NULL ORDER BY role`),
      query(`SELECT DISTINCT email_status FROM contacts WHERE email_status IS NOT NULL ORDER BY email_status`),
    ]);

    return NextResponse.json({
      states: statesRes.rows.map((r: { state: string }) => r.state),
      roles: rolesRes.rows.map((r: { role: string }) => r.role),
      emailStatuses: statusRes.rows.map((r: { email_status: string }) => r.email_status),
    });
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to fetch filter options", detail: String(err) },
      { status: 500 }
    );
  }
}
