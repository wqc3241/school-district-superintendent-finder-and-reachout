import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams;
    const page = Math.max(1, parseInt(params.get("page") || "1", 10));
    const size = Math.min(100, Math.max(1, parseInt(params.get("size") || "20", 10)));
    const state = params.get("state") || null;
    const search = params.get("query") || null;
    const role = params.get("role") || null;
    const emailStatus = params.get("email_status") || null;

    const conditions: string[] = [];
    const values: (string | number | boolean)[] = [];
    let paramIndex = 1;

    if (state) {
      conditions.push(`d.state = $${paramIndex++}`);
      values.push(state);
    }

    if (search) {
      conditions.push(
        `(c.first_name ILIKE $${paramIndex} OR c.last_name ILIKE $${paramIndex} OR c.email ILIKE $${paramIndex} OR d.name ILIKE $${paramIndex})`
      );
      values.push(`%${search}%`);
      paramIndex++;
    }

    if (role) {
      conditions.push(`c.role = $${paramIndex++}`);
      values.push(role);
    }

    if (emailStatus) {
      conditions.push(`c.email_status = $${paramIndex++}`);
      values.push(emailStatus);
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
    const offset = (page - 1) * size;

    const countResult = await query(
      `SELECT COUNT(*) as total
       FROM contacts c
       JOIN districts d ON c.district_id = d.id
       ${whereClause}`,
      values
    );
    const total = parseInt(countResult.rows[0].total, 10);

    const dataResult = await query(
      `SELECT c.id, c.first_name, c.last_name, c.role, c.district_id,
              d.name as district_name, d.state,
              c.email, c.email_status, c.phone, c.confidence_score,
              c.created_at, c.updated_at
       FROM contacts c
       JOIN districts d ON c.district_id = d.id
       ${whereClause}
       ORDER BY c.last_name ASC, c.first_name ASC
       LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`,
      [...values, size, offset]
    );

    return NextResponse.json({
      items: dataResult.rows,
      total,
      page,
      size,
    });
  } catch (error) {
    console.error("Contacts API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch contacts", detail: String(error) },
      { status: 500 }
    );
  }
}
