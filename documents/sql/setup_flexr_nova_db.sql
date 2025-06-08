-- filename: setup_flexr_nova_db.sql

-- IMPORTANT: You must execute this script connected to a database OTHER THAN "flexr-nova" (e.g., "postgres").
-- For example: psql -U postgres -h localhost -p $PORT -f setup_flexr_nova_db.sql

-- 1. Create the database 'flexr-nova'
--    Note: CREATE DATABASE does NOT support IF NOT EXISTS in standard PostgreSQL.
--    If the database already exists, this command will error.
CREATE DATABASE "flexr-nova";


-- 2. Create the user (role) 'flexr' with the specified password.
--    'LOGIN' allows the role to be used for logging in.
--    'PASSWORD' sets the authentication password.
--    'IF NOT EXISTS' is supported for CREATE ROLE, making it idempotent.
CREATE ROLE flexr WITH
  LOGIN
  PASSWORD '12qwaszx'
  VALID UNTIL '2026-06-08 12:35:40 NZST'; -- Optional: Set an expiration date. Adjust as needed.


-- 3. Grant all privileges on the database 'flexr-nova' to the user 'flexr'.
--    This grants CONNECT privilege to the database.
GRANT ALL PRIVILEGES ON DATABASE "flexr-nova" TO flexr;

-- 4. Switch connection to the newly created database and set default privileges.
--    The \connect meta-command is specific to psql and will execute the rest
--    of the script connected to the new database as the new user.
--    This ensures that *future* objects created in the public schema by 'flexr'
--    will have privileges correctly set.
--    Alternatively, the superuser (postgres) can set default privileges FOR ROLE flexr.
\connect "flexr-nova";

--GRANT CREATE, USAGE ON SCHEMA public TO flexr;
GRANT ALL ON SCHEMA public TO flexr;