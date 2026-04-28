#!/bin/sh
# Optional host-side cron job. Inside the compose stack, the `cleanup` service
# already deletes files older than 10 minutes every 2 minutes. Use this if you
# prefer a host crontab entry instead.
#
# Add to crontab:
#   */2 * * * * /path/to/cleanup-cron.sh
find /tmp/downloads -type f -mmin +10 -delete 2>/dev/null || true
