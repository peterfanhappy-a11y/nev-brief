-- 0007: 给 articles_processed 加 simhash 列 + raw_id UNIQUE 约束
-- pipeline-service 需要 simhash 查询做聚类，raw_id UNIQUE 让 upsert 幂等
ALTER TABLE articles_processed ADD COLUMN IF NOT EXISTS simhash bigint;
CREATE INDEX IF NOT EXISTS idx_processed_simhash ON articles_processed(simhash);
ALTER TABLE articles_processed
    ADD CONSTRAINT articles_processed_raw_id_unique UNIQUE (raw_id);
