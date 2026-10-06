#!/bin/bash
set -e

sudo -u postgres psql -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'syamanah') THEN CREATE ROLE syamanah LOGIN PASSWORD 'SyamanahDb2026!' SUPERUSER; ELSE ALTER ROLE syamanah WITH PASSWORD 'SyamanahDb2026!' SUPERUSER; END IF; END \$\$;"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = 'market_intelligence'" | grep -q 1 || sudo -u postgres createdb -O syamanah market_intelligence

sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" /etc/postgresql/16/main/postgresql.conf
sudo sed -i "s/listen_addresses = 'localhost'/listen_addresses = '*'/g" /etc/postgresql/16/main/postgresql.conf

grep -q "host all syamanah 0.0.0.0/0 scram-sha-256" /etc/postgresql/16/main/pg_hba.conf || echo "host all syamanah 0.0.0.0/0 scram-sha-256" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf
grep -q "host all syamanah 0.0.0.0/0 md5" /etc/postgresql/16/main/pg_hba.conf || echo "host all syamanah 0.0.0.0/0 md5" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf

sudo systemctl restart postgresql
echo "Postgres setup completed successfully on VPS!"
