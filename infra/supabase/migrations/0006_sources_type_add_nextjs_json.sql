-- 0006_sources_type_add_nextjs_json.sql
-- 扩展 sources.type 枚举，新增 'nextjs_json'（用于懂车帝等 Next.js __NEXT_DATA__ 源）

ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_type_check;
ALTER TABLE sources ADD CONSTRAINT sources_type_check
    CHECK (type IN ('rss','api','html_scrape','rsshub','nextjs_json'));
