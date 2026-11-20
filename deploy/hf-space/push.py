#!/usr/bin/env python3
"""Unggah backend ke Hugging Face Space lewat API commit (bukan git push --force): isi Space diganti dalam SATU commit,
jadi riwayat commit lama tetap ada dan bisa dikembalikan. Alternatif untuk workflow .github/workflows/deploy-hf.yml.

    HF_TOKEN=hf_... uv run --no-project --with huggingface_hub python deploy/hf-space/push.py <pemilik>/<nama-space>

Perhatian: berkas yang tidak ada di bundel akan DIHAPUS dari Space (delete_patterns=["*"]); periksa isi Space dulu.
Variabel/secret Space (DATABASE_URL, CLERK_ISSUER, ...) tidak disentuh; atur di Space > Settings.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

if len(sys.argv) != 2 or "/" not in sys.argv[1]:
    sys.exit(__doc__)
token = os.environ.get("HF_TOKEN", "")
if not token:
    sys.exit("Isi HF_TOKEN (token HF dengan izin write).")
space = sys.argv[1]
root = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "space"
    subprocess.run([str(root / "deploy/hf-space/bundle.sh"), str(out)], check=True)
    api = HfApi(token=token)
    commit = api.upload_folder(folder_path=str(out), repo_id=space, repo_type="space", delete_patterns=["*"],
                               commit_message="Deploy MALAS API dari GitHub")
    print("commit:", commit.commit_url)
    print("stage:", api.get_space_runtime(space).stage)
