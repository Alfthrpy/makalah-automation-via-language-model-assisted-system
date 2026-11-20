#!/usr/bin/env python3
"""Verifikasi audio v6: sinkron SFX vs peristiwa visual, sambungan loop, gambar spektrogram/gelombang bertanda.

    uv run --no-project --with numpy --with scipy --with pillow python -I verify_audio.py <folder-v6>

Masukan : events.json, soundtrack.wav, $STEMS_DIR/sfx.wav, $STEMS_DIR/music.wav (stem di luar repo)
Keluaran: verify/sync.json, verify/sync-table.md, verify/spectrogram.png, verify/waveform.png, verify/sync-zoom.png
Onset dideteksi dari STEM SFX (tanpa musik) karena musik membuat deteksi ambang di master tidak andal.
Waktu visual = waktu bingkai pertama yang menampilkan peristiwa (semua peristiwa dibulatkan ke batas bingkai di index.html).
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.io import wavfile

DIR = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(DIR, 'verify')
EVJ = json.load(open(os.path.join(DIR, 'events.json')))
FPS = EVJ['fps']
STEMS = os.environ.get('STEMS_DIR', os.path.join(V, 'stems'))
SR, sfx = wavfile.read(os.path.join(STEMS, 'sfx.wav'))
_, music = wavfile.read(os.path.join(STEMS, 'music.wav'))
_, master = wavfile.read(os.path.join(DIR, 'soundtrack.wav'))
N = len(master)
T = N / SR
mono = np.abs(sfx).max(axis=1)
FONT = ImageFont.truetype(os.path.join(DIR, 'fonts', 'Carlito-Regular.ttf'), 18)


def onset(t, pre=0.012, win=0.045):
    """Sampel pertama (setelah t-pre) yang melewati ambang: 15% puncak lokal di [t-pre, t+win],
    dan minimal 3x 'latar' (puncak ekor bunyi sebelumnya di [t-40 ms, t-15 ms])."""
    a, b = int((t - pre) * SR), int((t + win) * SR)
    seg = mono[a:b]
    bg = mono[int((t - min(0.04, pre + 0.028)) * SR):int((t - pre - 0.0005) * SR)].max()
    thr = max(0.15 * seg.max(), 3 * bg)
    i = int(np.argmax(seg > thr))
    return (a + i) / SR


from scipy import signal  # noqa: E402
HF = np.abs(signal.sosfilt(signal.butter(4, 4000, 'highpass', fs=SR, output='sos'), sfx.mean(axis=1)))


def onset_hf(t, pre=0.004, win=0.03):
    """Untuk ketukan tombol (jarak antar-ketukan bisa 1 bingkai): pakai transien frekuensi tinggi (>4 kHz),
    yang meluruh ~3,5 ms sehingga ekor ketukan sebelumnya sudah hilang."""
    a, b = int((t - pre) * SR), int((t + win) * SR)
    seg = HF[a:b]
    i = int(np.argmax(seg > 0.3 * seg.max()))
    return (a + i) / SR


rows = []
for e in EVJ['events']:
    vis = round(e['t'] * FPS) / FPS                      # bingkai pertama yang menampilkan peristiwa
    # ketukan tombol berjarak >= 1 bingkai; jendela latar dipersempit agar ekor ketukan sebelumnya tidak terbaca
    on = onset_hf(e['t']) if e['type'] == 'type' else onset(e['t'])
    rows.append(dict(type=e['type'], visual_s=round(vis, 4), frame=round(vis * FPS), onset_s=round(on, 4),
                     delta_ms=round((on - vis) * 1000, 1)))
deltas = np.array([r['delta_ms'] for r in rows])
summary = dict(events=len(rows), max_abs_delta_ms=float(np.abs(deltas).max()), mean_delta_ms=float(deltas.mean()),
               all_under_one_frame=bool((np.abs(deltas) < 1000 / FPS).all()))

# sambungan loop
ms10 = int(0.01 * SR)
rms = lambda x: float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12))
seam = dict(
    master_last10ms_dbfs=rms(master[-ms10:]), master_first10ms_dbfs=rms(master[:ms10]),
    master_jump_last_to_first=float(np.abs(master[-1] - master[0]).max()),
    music_last10ms_dbfs=rms(music[-ms10:]), music_first10ms_dbfs=rms(music[:ms10]),
    music_jump_last_to_first=float(np.abs(music[-1] - music[0]).max()),
    music_typical_sample_step=float(np.abs(np.diff(music, axis=0)).mean()),
)
# lonjakan antar-sampel terbesar di master (indikasi klik)
d = np.abs(np.diff(master, axis=0)).max(axis=1)
seam['master_max_sample_step'] = float(d.max())
seam['master_max_sample_step_at_s'] = float(d.argmax() / SR)

json.dump(dict(summary=summary, seam=seam, rows=rows), open(os.path.join(V, 'sync.json'), 'w'), indent=1)
with open(os.path.join(V, 'sync-table.md'), 'w') as f:
    f.write('| peristiwa | bingkai | waktu visual (dtk) | onset SFX (dtk) | selisih (ms) |\n|---|---|---|---|---|\n')
    for r in rows:
        f.write(f"| {r['type']} | {r['frame']} | {r['visual_s']:.3f} | {r['onset_s']:.4f} | {r['delta_ms']:+.1f} |\n")
print(json.dumps(dict(summary=summary, seam=seam), indent=1))

# spektrogram & gelombang (ffmpeg) + penanda peristiwa
W = 2700
COL = {'thud': (255, 80, 80), 'whoosh': (120, 200, 255), 'type': (180, 180, 180), 'tick': (120, 255, 140),
       'click': (255, 220, 90), 'ding': (255, 140, 255), 'swipe': (255, 235, 60), 'stamp': (255, 150, 60),
       'plop': (160, 255, 220), 'pop': (120, 230, 255), 'blip': (200, 200, 255), 'note1': (255, 190, 120), 'note2': (255, 120, 120), 'press': (255, 255, 255),
       'notif': (255, 200, 100), 'sent': (130, 170, 255), 'recv': (170, 255, 170), 'ting': (255, 230, 150), 'scratch': (255, 100, 200), 'tada': (255, 255, 120)}
src = os.path.join(DIR, 'soundtrack.wav')
for name, filt, H in (('spectrogram', f'showspectrumpic=s={W}x512:legend=0:scale=log:fscale=log:color=intensity', 512),
                      ('waveform', f'showwavespic=s={W}x400:split_channels=0:colors=0x9fb4ff', 400)):
    out = os.path.join(V, name + '.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-lavfi', filt, '-frames:v', '1', out], check=True)
    im = Image.open(out).convert('RGB')
    im2 = Image.new('RGB', (im.width, im.height + 60), (16, 18, 26))
    im2.paste(im, (0, 0))
    dr = ImageDraw.Draw(im2)
    for s in range(0, int(T) + 1):
        x = s / T * im.width
        dr.line([(x, im.height), (x, im.height + 8)], fill=(200, 200, 200))
        dr.text((x + 2, im.height + 8), f'{s}s', fill=(200, 200, 200), font=FONT)
    for r in rows:
        x = r['visual_s'] / T * im.width
        c = COL[r['type']]
        dr.line([(x, 0), (x, im.height)], fill=c if r['type'] != 'blip' else (90, 90, 90), width=1)
        if r['type'] != 'blip':
            dr.text((x + 3, im.height + 32), r['type'], fill=c, font=FONT)
    im2.save(out)

# zoom per peristiwa penting: gelombang stem SFX +-120 ms, garis putih = bingkai visual, kuning = onset terdeteksi
key = [r for r in rows if r['type'] != 'blip'] + [r for r in rows if r['type'] == 'blip'][:3]
cw, ch = 300, 150
cols = 5
im = Image.new('RGB', (cols * cw, ((len(key) + cols - 1) // cols) * (ch + 26)), (16, 18, 26))
dr = ImageDraw.Draw(im)
for k, r in enumerate(key):
    ox, oy = (k % cols) * cw, (k // cols) * (ch + 26)
    a = int((r['visual_s'] - 0.12) * SR)
    seg = mono[a:a + int(0.24 * SR)]
    seg = seg / (seg.max() + 1e-9)
    xs = np.linspace(0, cw - 1, len(seg)).astype(int)
    for x in range(cw):
        v = seg[xs == x].max() if (xs == x).any() else 0
        dr.line([(ox + x, oy + ch - 1), (ox + x, oy + ch - 1 - v * (ch - 10))], fill=COL[r['type']])
    vx = ox + cw / 2
    dr.line([(vx, oy), (vx, oy + ch)], fill=(255, 255, 255), width=2)
    sx = ox + (r['onset_s'] - (r['visual_s'] - 0.12)) / 0.24 * cw
    dr.line([(sx, oy), (sx, oy + ch)], fill=(255, 230, 0), width=1)
    dr.text((ox + 4, oy + ch + 3), f"{r['type']} @{r['visual_s']:.3f}s  {r['delta_ms']:+.1f} ms", fill=(230, 230, 230), font=FONT)
im.save(os.path.join(V, 'sync-zoom.png'))
