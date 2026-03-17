import { NextResponse } from "next/server";

export async function GET() {
  // No activity tracking in DB yet — return empty array
  return NextResponse.json([]);
}
