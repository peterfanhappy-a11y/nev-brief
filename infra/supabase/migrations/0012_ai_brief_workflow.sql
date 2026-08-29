-- 0012_ai_brief_workflow.sql
-- Explicit publication lifecycle for public AIVIZENS daily archives.

ALTER TABLE ai_daily_briefs
  ADD COLUMN status text NOT NULL DEFAULT 'generating'
    CHECK (status IN ('generating','blocked','awaiting_approval','approved','published')),
  ADD COLUMN quality_report jsonb,
  ADD COLUMN digest_sources jsonb,
  ADD COLUMN approved_at timestamptz,
  ADD COLUMN published_at timestamptz,
  ADD COLUMN failure_reason text;

-- Historical documents predate the workflow and require fresh review. Preserve
-- their content, but fail closed: none becomes public through this migration.
UPDATE ai_daily_briefs
SET status = 'awaiting_approval',
    quality_report = jsonb_build_object(
      'passed', false,
      'blockers', '[]'::jsonb,
      'warnings', jsonb_build_array(
        jsonb_build_object(
          'code', 'pre_workflow_import',
          'message', 'Imported before publication workflow; regenerate and review before approval.',
          'path', NULL
        )
      ),
      'metrics', jsonb_build_object('pre_workflow_import', true)
    );

CREATE INDEX idx_ai_daily_briefs_public
  ON ai_daily_briefs(published_at DESC)
  WHERE status = 'published';
