import { PGlite } from "@electric-sql/pglite";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const migrationPath = resolve(
  process.cwd(),
  "../supabase/migrations/202607280001_beginner_mode_preference.sql",
);

describe("Beginner Mode preference migration", () => {
  it("applies compatibly and rolls back cleanly in an isolated PostgreSQL database", async () => {
    const database = new PGlite();
    await database.exec(`
      create table user_settings (
        user_id uuid primary key,
        default_account_size numeric not null default 10000,
        default_risk_percent numeric not null default 1,
        preferred_currency text not null default 'USD',
        theme text not null default 'dark'
      );
      insert into user_settings (user_id) values ('00000000-0000-0000-0000-000000000001');
    `);
    await database.exec("begin");
    await database.exec(await readFile(migrationPath, "utf8"));
    const rows = await database.query<{ experience_mode: string }>(
      "select experience_mode from user_settings",
    );
    expect(rows.rows).toEqual([{ experience_mode: "advanced" }]);
    await expect(database.exec(
      "insert into user_settings (user_id, experience_mode) values ('00000000-0000-0000-0000-000000000002', 'invalid')",
    )).rejects.toThrow();
    await database.exec("rollback");
    const columns = await database.query<{ column_name: string }>(
      "select column_name from information_schema.columns where table_name = 'user_settings' and column_name = 'experience_mode'",
    );
    expect(columns.rows).toEqual([]);
    const preserved = await database.query<{ count: number }>(
      "select count(*)::int as count from user_settings",
    );
    expect(preserved.rows).toEqual([{ count: 1 }]);
    await database.close();
  });
});
