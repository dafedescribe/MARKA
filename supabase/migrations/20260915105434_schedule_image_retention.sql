create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

select cron.schedule(
  'cleanup-expired-images',
  '*/15 * * * *',
  $job$
  select net.http_post(
    url := rtrim(
      (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'project_url'
      ),
      '/'
    ) || '/functions/v1/cleanup-expired-images',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'X-Cleanup-Secret',
      (
        select decrypted_secret
        from vault.decrypted_secrets
        where name = 'cleanup_cron_secret'
      )
    ),
    body := jsonb_build_object('dry_run', false),
    timeout_milliseconds := 60000
  ) as request_id;
  $job$
);
