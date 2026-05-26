-- 0004_rls_policies.sql
-- Spec §4.4 §7.6

-- Create Supabase roles for local dev (safe if they exist)
DO $$ BEGIN
  CREATE ROLE anon NOINHERIT;
EXCEPTION WHEN duplicate_object THEN END;
$$;

DO $$ BEGIN
  CREATE ROLE authenticated NOINHERIT;
EXCEPTION WHEN duplicate_object THEN END;
$$;

DO $$ BEGIN
  CREATE ROLE service_role NOINHERIT;
EXCEPTION WHEN duplicate_object THEN END;
$$;

-- 启用所有表的 RLS
ALTER TABLE subscribers              ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriber_preferences   ENABLE ROW LEVEL SECURITY;
ALTER TABLE sources                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles_raw             ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles_processed       ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_briefs             ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicle_sales_daily      ENABLE ROW LEVEL SECURITY;
ALTER TABLE deliveries               ENABLE ROW LEVEL SECURITY;

-- 所有表禁止 anon role 任何操作
-- service_role 自动绕过 RLS（Postgres 默认行为）
-- 即所有应用层访问必须用 service_role key（在 .env 中）

-- 唯一例外：sources 表允许 anon SELECT（公开信源清单）
CREATE POLICY anon_read_sources_enabled
    ON sources FOR SELECT
    TO anon
    USING (enabled = true);

-- 不为其他表创建任何 anon policy → 默认拒绝所有
