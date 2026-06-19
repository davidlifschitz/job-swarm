-- Per-user row level security for hosted Supabase deployments.
-- Service role and direct DATABASE_URL connections bypass RLS for workers.

ALTER TABLE resume_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE target_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE preference_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE linkedin_connection_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE linkedin_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_packets ENABLE ROW LEVEL SECURITY;
ALTER TABLE fit_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE rules_filter_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE cloud_run_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY resume_assets_owner ON resume_assets
  FOR ALL TO authenticated
  USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);

CREATE POLICY target_profiles_owner ON target_profiles
  FOR ALL TO authenticated
  USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);

CREATE POLICY preference_answers_owner ON preference_answers
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = preference_answers.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = preference_answers.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  );

CREATE POLICY linkedin_connection_imports_owner ON linkedin_connection_imports
  FOR ALL TO authenticated
  USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);

CREATE POLICY linkedin_connections_owner ON linkedin_connections
  FOR ALL TO authenticated
  USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);

CREATE POLICY job_decisions_owner ON job_decisions
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = job_decisions.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = job_decisions.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  );

CREATE POLICY application_packets_owner ON application_packets
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = application_packets.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = application_packets.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  );

CREATE POLICY fit_reviews_owner ON fit_reviews
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = fit_reviews.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = fit_reviews.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  );

CREATE POLICY rules_filter_results_owner ON rules_filter_results
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = rules_filter_results.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM target_profiles
      WHERE target_profiles.id = rules_filter_results.target_profile_id
        AND target_profiles.user_id = auth.uid()::text
    )
  );

CREATE POLICY cloud_runs_owner ON cloud_runs
  FOR ALL TO authenticated
  USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);

CREATE POLICY cloud_run_events_owner ON cloud_run_events
  FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM cloud_runs
      WHERE cloud_runs.id = cloud_run_events.run_id
        AND cloud_runs.user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM cloud_runs
      WHERE cloud_runs.id = cloud_run_events.run_id
        AND cloud_runs.user_id = auth.uid()::text
    )
  );