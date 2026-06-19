-- Create bucket in Supabase Dashboard → Storage → New bucket: resume-assets (private)
-- Then apply these policies (service role bypasses RLS for worker uploads).

-- Authenticated users can read their own resume files.
CREATE POLICY "resume_assets_read_own"
ON storage.objects FOR SELECT
TO authenticated
USING (
  bucket_id = 'resume-assets'
  AND (storage.foldername(name))[1] = auth.uid()::text
);

-- Authenticated users can upload into their own folder.
CREATE POLICY "resume_assets_insert_own"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'resume-assets'
  AND (storage.foldername(name))[1] = auth.uid()::text
);