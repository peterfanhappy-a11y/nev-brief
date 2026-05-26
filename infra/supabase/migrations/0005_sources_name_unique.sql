-- 0005_sources_name_unique.sql
-- 为 source_loader.upsert 提供 ON CONFLICT 目标
ALTER TABLE sources ADD CONSTRAINT sources_name_unique UNIQUE (name);
