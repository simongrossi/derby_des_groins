#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_TOKEN:?Set GITHUB_TOKEN with repo:actions scope}"
: "${GITHUB_REPOSITORY:?Set GITHUB_REPOSITORY as owner/repo}"

echo "==> Triggering GitHub Actions deploy workflow via repository_dispatch"
curl -fsS -X POST "https://api.github.com/repos/${GITHUB_REPOSITORY}/dispatches" \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -d '{"event_type":"deploy"}'

echo "✅ Deploy event sent."
