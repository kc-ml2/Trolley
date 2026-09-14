-- Local development defaults. Change passwords before non-local deployment.
-- The catalog and query Target are separate databases with separate privileges.
CREATE ROLE trolley_catalog LOGIN PASSWORD 'trolley_catalog_password';
ALTER DATABASE trolley OWNER TO trolley_catalog;
REVOKE CONNECT, TEMPORARY ON DATABASE trolley FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE trolley TO trolley_catalog;

CREATE DATABASE trolley_data OWNER trolley;
CREATE ROLE trolley_reader LOGIN PASSWORD 'trolley_reader_password';
REVOKE CONNECT, TEMPORARY ON DATABASE trolley_data FROM PUBLIC;
GRANT CONNECT ON DATABASE trolley_data TO trolley_reader;
ALTER ROLE trolley_reader SET default_transaction_read_only = on;

\connect trolley_data
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO trolley_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO trolley_reader;
-- Applies to tables subsequently created by the local provisioning role.
ALTER DEFAULT PRIVILEGES FOR ROLE trolley IN SCHEMA public
    GRANT SELECT ON TABLES TO trolley_reader;
