#!/usr/bin/env bash
# Menyusun isi Space (sub-set repo) di folder keluaran, siap di-push ke repo git Space.
#   deploy/hf-space/bundle.sh <folder-keluaran>
# Isi: Dockerfile (salinan apps/api/Dockerfile) di root, README.md berfront-matter HF, pyproject.toml + uv.lock,
# packages/engine, apps/api (tanpa tes, cache, dan berkas .env).
set -euo pipefail
out="${1:?pakai: bundle.sh <folder-keluaran>}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
rm -rf "$out"
mkdir -p "$out/packages" "$out/apps"
cp -r "$root/packages/engine" "$out/packages/engine"
cp -r "$root/apps/api" "$out/apps/api"
find "$out" \( -name __pycache__ -o -name tests -o -name .pytest_cache -o -name .venv \) -prune -exec rm -rf {} +
find "$out" \( -name '.env' -o -name '.env.*' \) ! -name '.env.example' -delete
cp "$root/pyproject.toml" "$root/uv.lock" "$root/.dockerignore" "$out/"
cp "$root/apps/api/Dockerfile" "$out/Dockerfile"
cp "$root/deploy/hf-space/README.md" "$out/README.md"
echo "Bundel Space siap di $out"
