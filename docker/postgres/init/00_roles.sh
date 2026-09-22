#!/bin/sh
set -eu

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=agent_password="$POSTGRES_AGENT_PASSWORD" --set=database_name="$POSTGRES_DB" <<'SQL'
SELECT format('CREATE ROLE rolelens_agent_ro LOGIN PASSWORD %L', :'agent_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rolelens_agent_ro') \gexec
ALTER ROLE rolelens_agent_ro SET default_transaction_read_only = on;
SELECT format('GRANT CONNECT ON DATABASE %I TO rolelens_agent_ro', :'database_name') \gexec
SQL
