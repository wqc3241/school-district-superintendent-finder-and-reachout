import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET(request: NextRequest) {
  try {
    const params = request.nextUrl.searchParams;
    const page = Math.max(1, parseInt(params.get("page") || "1", 10));
    const size = Math.min(100, Math.max(1, parseInt(params.get("size") || "20", 10)));
    const state = params.get("state") || null;
    const search = params.get("query") || null;
    const eslOnly = params.get("esl_only") === "true";
    const titleIOnly = params.get("title_i_only") === "true";
    const fundingType = params.get("funding_type") || null;

    const conditions: string[] = [];
    const values: (string | number | boolean)[] = [];
    let paramIndex = 1;

    if (state) {
      conditions.push(`state = $${paramIndex++}`);
      values.push(state);
    }

    if (search) {
      conditions.push(`(name ILIKE $${paramIndex} OR city ILIKE $${paramIndex})`);
      values.push(`%${search}%`);
      paramIndex++;
    }

    if (eslOnly) {
      conditions.push(`esl_program_status = true`);
    }

    if (titleIOnly) {
      conditions.push(`title_i_status = true`);
    }

    if (fundingType === "title_i") {
      conditions.push(`title_i_status = true`);
    } else if (fundingType === "title_iii") {
      conditions.push(`title_iii_allocation > 0`);
    } else if (fundingType === "both") {
      conditions.push(`title_i_status = true AND title_iii_allocation > 0`);
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
    const offset = (page - 1) * size;

    const countResult = await query(
      `SELECT COUNT(*) as total FROM districts ${whereClause}`,
      values
    );
    const total = parseInt(countResult.rows[0].total, 10);

    const dataResult = await query(
      `SELECT id, nces_id, name, state, city, address, zip_code, phone, website,
              esl_program_status, ell_student_count, ell_percentage,
              title_i_status, title_i_allocation, title_iii_allocation,
              created_at, updated_at
       FROM districts ${whereClause}
       ORDER BY name ASC
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
    console.error("Districts API error:", error);
    return NextResponse.json(
      { error: "Failed to fetch districts", detail: String(error) },
      { status: 500 }
    );
  }
}
