import { NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const table = url.searchParams.get("from") || "districts";

  try {
    let result;
    if (table === "contacts") {
      // Get distinct states that have contacts
      result = await query(
        `SELECT DISTINCT d.state FROM contacts c JOIN districts d ON c.district_id = d.id WHERE d.state IS NOT NULL ORDER BY d.state`
      );
    } else {
      // Get distinct states from districts
      result = await query(
        `SELECT DISTINCT state FROM districts WHERE state IS NOT NULL ORDER BY state`
      );
    }
    const states = result.rows.map((r: { state: string }) => r.state);
    return NextResponse.json(states);
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to fetch states", detail: String(err) },
      { status: 500 }
    );
  }
}
