#!/usr/bin/env python3
"""Hitung sampel clip di soundtrack.wav dan di audio AAC hasil mux, serta offset AAC vs WAV (korelasi silang).
    uv run --no-project --with numpy --with scipy python -I check_mux.py <folder-v4>"""
import json
import os
import subprocess
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

DIR = os.path.abspath(sys.argv[1])
sr, wav = wavfile.read(os.path.join(DIR, 'soundtrack.wav'))
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(DIR, 'malas-promo-v4.mp4'), '-map', '0:a',
                      '-f', 'f32le', '-ac', '2', '-ar', str(sr), '-'], capture_output=True, check=True).stdout
aac = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
a, b = wav[: sr * 4, 0], aac[: sr * 4, 0]
xc = signal.correlate(b, a, mode='full', method='fft')
lag = int(xc.argmax() - (len(a) - 1))
out = dict(wav_samples=len(wav), aac_samples=len(aac), length_diff_ms=(len(aac) - len(wav)) / sr * 1000,
           wav_clipped_samples=int((np.abs(wav) >= 1.0).sum()), aac_clipped_samples=int((np.abs(aac) >= 1.0).sum()),
           wav_peak=float(np.abs(wav).max()), aac_peak=float(np.abs(aac).max()), aac_vs_wav_offset_ms=lag / sr * 1000)
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(DIR, 'verify', 'mux-check.json'), 'w'), indent=1)
