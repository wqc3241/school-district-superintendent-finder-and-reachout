import { Pool } from "pg";

// Strip sslmode from connection string — pg module handles SSL via the ssl option
const connString = (process.env.DATABASE_URL || "").replace(/[?&]sslmode=[^&]*/g, "");

// Use connection pooling for serverless environments
const pool = new Pool({
  connectionString: connString,
  ssl: { rejectUnauthorized: false },
  max: 3,
});

export async function query(text: string, params?: (string | number | boolean | null)[]) {
  const client = await pool.connect();
  try {
    const result = await client.query(text, params);
    return result;
  } finally {
    client.release();
  }
}
