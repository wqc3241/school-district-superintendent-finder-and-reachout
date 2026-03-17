import { NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET() {
  try {
    const [statesRes, fundingRes] = await Promise.all([
      query(`SELECT DISTINCT state FROM districts WHERE state IS NOT NULL ORDER BY state`),
      query(`
        SELECT
          COUNT(*) FILTER (WHERE esl_program_status = true) AS esl_count,
          COUNT(*) FILTER (WHERE esl_program_status = false OR esl_program_status IS NULL) AS no_esl_count,
          COUNT(*) FILTER (WHERE title_i_status = true AND (esl_program_status = false OR esl_program_status IS NULL)) AS title_i_only_count,
          COUNT(*) FILTER (WHERE esl_program_status = true AND (title_i_status = false OR title_i_status IS NULL)) AS title_iii_only_count,
          COUNT(*) FILTER (WHERE title_i_status = true AND esl_program_status = true) AS both_count
        FROM districts
      `),
    ]);

    const stats = fundingRes.rows[0];

    // Build ESL program options dynamically based on what exists
    const eslOptions: { value: string; label: string }[] = [
      { value: "all", label: "All Programs" },
    ];
    if (Number(stats.esl_count) > 0) {
      eslOptions.push({ value: "yes", label: `Has ESL (${Number(stats.esl_count).toLocaleString()})` });
    }
    if (Number(stats.no_esl_count) > 0) {
      eslOptions.push({ value: "no", label: `No ESL (${Number(stats.no_esl_count).toLocaleString()})` });
    }

    // Build funding type options — mutually exclusive counts
    const fundingOptions: { value: string; label: string }[] = [
      { value: "all", label: "All Funding" },
    ];
    if (Number(stats.title_i_only_count) > 0) {
      fundingOptions.push({ value: "title_i", label: `Title I Only (${Number(stats.title_i_only_count).toLocaleString()})` });
    }
    if (Number(stats.title_iii_only_count) > 0) {
      fundingOptions.push({ value: "title_iii", label: `Title III Only (${Number(stats.title_iii_only_count).toLocaleString()})` });
    }
    if (Number(stats.both_count) > 0) {
      fundingOptions.push({ value: "both", label: `Title I & III (${Number(stats.both_count).toLocaleString()})` });
    }

    return NextResponse.json({
      states: statesRes.rows.map((r: { state: string }) => r.state),
      eslOptions,
      fundingOptions,
    });
  } catch (err) {
    return NextResponse.json(
      { error: "Failed to fetch district filter options", detail: String(err) },
      { status: 500 }
    );
  }
}
