#!/bin/bash
BACKUP_DIR="/home/syamanah/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/market_intelligence_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"
PGPASSWORD="SyamanahDb2026!" pg_dump -h localhost -U syamanah market_intelligence | gzip > "${BACKUP_FILE}"

# Hapus backup yang lebih dari 14 hari
find "${BACKUP_DIR}" -name "*.sql.gz" -mtime +14 -delete
echo "[$(date)] Backup completed: ${BACKUP_FILE} ($(du -h ${BACKUP_FILE} | cut -f1))"
