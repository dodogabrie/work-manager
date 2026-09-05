#!/bin/bash
# Backup di PostgreSQL. Da mettere in cron:
#   0 3 * * * /percorso/work-planner/backup.sh
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p backups
STAMP=$(date +%Y%m%d-%H%M%S)

docker compose exec -T db pg_dump -U "${POSTGRES_USER:-workplanner}" \
  "${POSTGRES_DB:-workplanner}" | gzip > "backups/workplanner-$STAMP.sql.gz"

# Trattiene 30 giorni: un backup che riempie il disco è un backup che smette
# di esistere proprio quando serve.
find backups -name 'workplanner-*.sql.gz' -mtime +30 -delete

echo "backup: backups/workplanner-$STAMP.sql.gz"
