-- Mirror the Supabase service-role boundary for the isolated PostgREST test API.
ALTER ROLE service_role BYPASSRLS;
GRANT service_role TO nev_test;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO service_role;
