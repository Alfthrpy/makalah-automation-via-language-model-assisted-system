#!/usr/bin/env python3
"""Soundtrack orisinal MALAS promo v4: musik lo-fi + SFX, disintesis lokal (tanpa sampel, tanpa internet).

Jalankan (lewat build.sh, atau langsung):
    uv run --no-project --with numpy --with scipy python -I audio.py <folder-v4>

Masukan : <folder-v4>/events.json  (ditulis render.cjs dari window.TIMELINE + window.EVENTS di index.html)
Keluaran: soundtrack.wav (master, 48 kHz stereo float32), sfx/*.wav (tiap SFX satu berkas),
          $STEMS_DIR/{music,sfx}.wav (stem analisis; default di luar repo), verify/loudness-internal.json

Desain singkat
- Tempo 86,02 BPM, 4/4, 44 ketukan = 30,7 dtk = panjang video (v3: 40 ketukan). Kunci F mayor.
- Akor per bar: Fmaj7 | Dm7 | Gm7 | C9 | Fmaj7 | Dm7 | Gm7 | C9 | Gm7 | C9sus4 | Fmaj7 (mendarat) -> loop ke Fmaj7.
- v4 (ending): bar 1-9 sama dengan v3. Drum berhenti setengah ketukan sebelum tombol ditekan ("tarikan napas"),
  dua nada naik C5 -> F5 (tonika) dengan F5 tepat di momen tekan, akor Fmaj7 mendarat + kick lembut, lalu bar
  terakhir hanya pad/e-piano/bas/hat tipis yang meluruh dan menyambung ke intro hook (juga Fmaj7).
- Instrumen: e-piano FM (chorus + tremolo), pad harmonik ber-low-pass, bas sinus, kick/snare/rim/hat sintetis,
  vinyl crackle sangat halus. Reverb = konvolusi dengan derau yang meluruh.
- Seluruh musik dirender MELINGKAR (ekor nada/reverb di akhir dibungkus ke awal), jadi loop menyambung tanpa
  lompatan; fade 80 ms di awal / 120 ms di akhir hanya untuk pemutaran pertama dan akhir berkas.
- Aransemen mengikuti adegan: hook minimal (pad+bas), "Ketik judul" beat tipis, "Mode uji -> MALAS nyusun -> .docx"
  penuh, "DRAF / aturan kampus" melunak (tanpa kick/snare), callback 14 tab + tagline + end card penuh, lalu
  resolusi di tombol (lihat di atas).
- SFX ditempatkan sampel-akurat pada waktu peristiwa dari events.json + 1/2 bingkai (bingkai visual pertama
  yang berubah adalah bingkai peristiwa atau sesudahnya; +16,7 ms membuat selisih maksimum 1/2 bingkai).
- Mixing: HPF 30 Hz, ducking musik halus saat SFX penting, master -14 LUFS terintegrasi, true peak <= -1 dBTP
  (gain linear terukur + limiter look-ahead bila perlu), tanpa clipping.
"""
import json
import os
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d

SR = 48000
DIR = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
EVJ = json.load(open(os.path.join(DIR, 'events.json')))
TL, EVENTS, FPS = EVJ['timeline'], EVJ['events'], EVJ['fps']
FRAMES = EVJ['frames']
N = FRAMES * SR // FPS                      # sampel = durasi video persis (837 bingkai -> 1.339.200 sampel)
T = N / SR
BEAT = TL['BEAT']
SC = TL['SC']
SFX_SHIFT = 0.5 / FPS                       # +1/2 bingkai (lihat docstring)
PRESS = next(e['t'] for e in EVENTS if e['type'] == 'press')
STEMS = os.environ.get('STEMS_DIR', os.path.join(DIR, 'verify', 'stems'))
rng = np.random.default_rng(20261120)       # deterministik


# ---------------------------------------------------------------- utilitas
def tt(n):
    return np.arange(n) / SR


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def fade(x, a=0.002, r=0.015):
    """Fade sangat singkat di kedua ujung: tidak ada klik di awal/akhir sebuah bunyi."""
    x = x.copy()
    na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    x[:na] *= np.linspace(0, 1, na)[:, None] if x.ndim == 2 else np.linspace(0, 1, na)
    x[-nr:] *= np.linspace(1, 0, nr)[:, None] if x.ndim == 2 else np.linspace(1, 0, nr)
    return x


def st(x, pan=0.0):
    """Mono -> stereo dengan pan hukum daya-sama (pan -1..1)."""
    th = (pan + 1) * np.pi / 4
    return np.stack([x * np.cos(th), x * np.sin(th)], axis=1)


def place(buf, t0, x):
    """Tambah x ke buf mulai detik t0, MELINGKAR (bagian yang lewat akhir dibungkus ke awal)."""
    s = int(round(t0 * SR)) % N
    n = len(x)
    while n > 0:
        k = min(n, N - s)
        buf[s:s + k] += x[len(x) - n:len(x) - n + k]
        n -= k
        s = 0


def sos(kind, f, order=2):
    return signal.butter(order, f, btype=kind, fs=SR, output='sos')


def filt(x, s):
    return signal.sosfilt(s, x, axis=0)


def circ_filt(x, s):
    """Filter kausal pada sinyal periodik: saring 3 salinan, ambil yang tengah (keadaan tunak, tanpa jahitan)."""
    y = signal.sosfilt(s, np.concatenate([x, x, x], axis=0), axis=0)
    return y[len(x):2 * len(x)]


def noise(n):
    return rng.standard_normal(n)


# ---------------------------------------------------------------- instrumen musik
def epiano(f, dur, vel):
    """E-piano FM: pembawa + modulator 1:1 dengan indeks meluruh, 'tine' halus, chorus L/R, tremolo pelan."""
    n = int((dur + 1.4) * SR)
    t = tt(n)
    idx = 1.1 * np.exp(-t / 0.35) + 0.15
    out = []
    for cents, ph in ((-4, 0.0), (4, np.pi * 0.7)):
        ff = f * 2 ** (cents / 1200)
        x = np.sin(2 * np.pi * ff * t + idx * np.sin(2 * np.pi * ff * t))
        x += 0.12 * np.sin(2 * np.pi * ff * 4.0 * t) * np.exp(-t / 0.05)
        x *= 1 + 0.12 * np.sin(2 * np.pi * 4.2 * t + ph)
        out.append(x)
    env = np.minimum(1, t / 0.004) * np.exp(-t / 1.5)
    off = t > dur
    env[off] *= np.exp(-(t[off] - dur) / 0.12)
    y = np.stack(out, axis=1) * env[:, None] * vel
    return fade(filt(y, sos('lowpass', 3800)), 0.001, 0.05)


def pad(freqs, dur):
    n = int((dur + 1.2) * SR)
    t = tt(n)
    y = np.zeros((n, 2))
    for f in freqs:
        for ch, cents in ((0, -7), (1, 7)):
            ff = f * 2 ** (cents / 1200)
            x = sum(np.sin(2 * np.pi * ff * k * t + k) / k ** 1.4 for k in range(1, 7))
            y[:, ch] += x
    env = np.minimum(1, t / 0.6)
    off = t > dur
    env[off] *= np.exp(-(t[off] - dur) / 0.35)
    y *= env[:, None] / len(freqs)
    return fade(filt(y, sos('lowpass', 1400)), 0.001, 0.08)


def bass(f, dur, vel):
    n = int((dur + 0.3) * SR)
    t = tt(n)
    x = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(4 * np.pi * f * t) + 0.06 * np.sin(6 * np.pi * f * t)
    env = np.minimum(1, t / 0.008) * np.exp(-t / 0.9)
    off = t > dur
    env[off] *= np.exp(-(t[off] - dur) / 0.05)
    return fade(filt(x * env * vel, sos('lowpass', 420)), 0.001, 0.03)


def kick(vel):
    t = tt(int(0.45 * SR))
    f = 46 + 72 * np.exp(-t / 0.032)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.2)
    x += 0.15 * filt(noise(len(t)), sos('bandpass', [800, 3000])) * np.exp(-t / 0.003)
    return fade(x * vel, 0.0005, 0.03)


def snare(vel):
    t = tt(int(0.3 * SR))
    x = 0.55 * filt(noise(len(t)), sos('bandpass', [1200, 5200])) * np.exp(-t / 0.075)
    x += 0.45 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05)
    return fade(x * vel, 0.0005, 0.03)


def rim(vel):
    t = tt(int(0.09 * SR))
    x = 0.6 * np.sin(2 * np.pi * 1650 * t) * np.exp(-t / 0.012) + 0.4 * np.sin(2 * np.pi * 820 * t) * np.exp(-t / 0.016)
    x += 0.2 * filt(noise(len(t)), sos('highpass', 2500)) * np.exp(-t / 0.006)
    return fade(x * vel, 0.0005, 0.02)


def hat(vel):
    t = tt(int(0.09 * SR))
    x = filt(filt(noise(len(t)), sos('highpass', 7000)), sos('lowpass', 10500)) * np.exp(-t / 0.026)
    return fade(x * vel, 0.0005, 0.02)


# ---------------------------------------------------------------- aransemen
CHORDS = [  # (voicing MIDI, bas MIDI)
    ([53, 57, 60, 64], 41),  # Fmaj7
    ([50, 53, 57, 60], 38),  # Dm7
    ([55, 58, 62, 65], 43),  # Gm7
    ([52, 55, 58, 62], 36),  # C9 (tanpa akar)
] * 2 + [
    ([55, 58, 62, 65], 43),  # Gm7
    ([53, 55, 58, 62], 36),  # C9sus4
    ([53, 57, 60, 64], 41),  # Fmaj7: mendarat tepat saat tombol ditekan
]
BAR = 4 * BEAT
SWING = 0.58


def section(t):
    """Intensitas per kelompok instrumen menurut adegan (waktu dari index.html)."""
    if t < SC['A']:
        return dict(kick=0, snare=0, rim=0, hat=0, ep=0.55, bass=0.8, pad=1.0)        # hook: minimal
    if t < SC['B']:
        return dict(kick=0.7, snare=0, rim=0.45, hat=0.5, ep=0.8, bass=1.0, pad=0.9)   # mulai bergerak
    if t < SC['E']:
        return dict(kick=1, snare=1, rim=0, hat=1, ep=1, bass=1, pad=0.8)              # penuh
    if t < SC['F']:
        return dict(kick=0, snare=0, rim=0.5, hat=0.45, ep=0.75, bass=0.75, pad=1.0)   # DRAF: melunak
    if t < PRESS - 0.5 * BEAT:
        return dict(kick=1, snare=1, rim=0, hat=1, ep=1, bass=1, pad=0.8)              # callback + tagline + end card
    if t < PRESS:
        return dict(kick=0, snare=0, rim=0, hat=0, ep=0.7, bass=0.7, pad=1.0)          # tarikan napas sebelum tekan
    return dict(kick=0, snare=0, rim=0, hat=0.3, ep=0.85, bass=0.8, pad=1.0)           # mendarat, meluruh ke loop


def humanize(ms=5):
    return rng.uniform(-ms, ms) / 1000


def build_music():
    dry = np.zeros((N, 2))
    send = np.zeros((N, 2))      # kiriman reverb
    drums = np.zeros((N, 2))
    for bi, (voic, bnote) in enumerate(CHORDS):
        b0 = bi * BAR
        last = bi == len(CHORDS) - 1
        s = section(b0 + 0.01)
        # pad: akor sepanjang bar
        p = pad([mtof(m) for m in voic], BAR) * 0.11 * section(b0 + 0.01)['pad']
        place(dry, b0, p * 0.7)
        place(send, b0, p * 0.6)
        # e-piano: ketukan 1 dan "and" dari 2 (swing); hook hanya ketukan 1; bar terakhir menggantung
        hits = [(0.0, 1.4, 0.8), (1 + SWING, 1.0, 0.58)]
        if b0 < SC['A']:
            hits = [(0.0, 3.2, 0.6)]
        if last:
            hits = [(0.0, 3.4, 0.8)]                         # satu akor Fmaj7 panjang yang mendarat
        for pos, dur, vel in hits:
            t0 = b0 + pos * BEAT
            g = section(t0 + 0.01)['ep']
            for j, m in enumerate(sorted(voic)):
                x = epiano(mtof(m), dur * BEAT, vel * g * (0.9 + 0.1 * j / 3)) * 0.09
                place(dry, t0 + j * 0.006 + humanize(3), x)     # sedikit "strum"
                place(send, t0 + j * 0.006, x * 0.5)
        # bas
        bpat = [(0.0, 1.5, 1.0), (2.0, 0.9, 0.8), (3 + SWING, 0.32, 0.55)]
        if b0 < SC['A']:
            bpat = [(0.0, 3.6, 0.9)]
        elif SC['E'] <= b0 + 2 * BEAT < SC['F']:
            bpat = [(0.0, 3.0, 0.85)]
        if last:
            bpat = [(0.0, 3.7, 0.9)]
        for pos, dur, vel in bpat:
            t0 = b0 + pos * BEAT
            f = mtof(bnote + (7 if pos > 3 else 0))
            place(dry, t0, st(bass(f, dur * BEAT, vel * section(t0 + 0.01)['bass']) * 0.32))
        # drum per ketukan / 8-an berswing
        for beat in range(4):
            for half in (0, 1):
                pos = beat + (SWING if half else 0)
                t0 = b0 + pos * BEAT
                s = section(t0 + 0.001)
                if half == 0 and beat in (0,) and s['kick']:
                    place(drums, t0, st(kick(s['kick']) * 0.55))
                if half == 1 and beat == 1 and s['kick'] and s['snare']:
                    place(drums, t0, st(kick(0.55 * s['kick']) * 0.55))
                if half == 0 and beat == 2 and s['kick'] and not s['snare']:
                    place(drums, t0, st(kick(0.6 * s['kick']) * 0.55))
                if half == 0 and beat in (1, 3) and s['snare']:
                    x = st(snare(s['snare'] * (0.9 if beat == 1 else 1.0)) * 0.2, 0.08)
                    place(drums, t0 + humanize(4), x)
                    place(send, t0, x * 0.35)
                if half == 0 and beat in (1, 3) and s['rim']:
                    x = st(rim(s['rim']) * 0.12, 0.1)
                    place(drums, t0 + humanize(4), x)
                    place(send, t0, x * 0.5)
                if s['hat'] and (half == 1 or s['snare']):
                    v = (0.55 if half == 0 else 0.4) * s['hat'] * rng.uniform(0.85, 1.0)
                    place(drums, t0 + humanize(6), st(hat(v) * 0.05, -0.25))
    # kick lembut tepat di momen tekan (akor mendarat)
    place(drums, PRESS, st(kick(0.75) * 0.55))
    # vinyl crackle sangat halus (impuls jarang ber-low-pass)
    crack = np.zeros(N)
    for _ in range(int(T * 5)):
        i = rng.integers(0, N - 64)
        crack[i:i + 24] += rng.uniform(-1, 1) * np.exp(-np.arange(24) / 5)
    crack = circ_filt(crack, sos('bandpass', [900, 6000])) * 0.010
    music = dry + drums + st(crack, 0.0)
    # reverb: konvolusi melingkar dengan IR derau meluruh (dekorelasi L/R), pre-delay 18 ms
    nir = int(1.9 * SR)
    tir = tt(nir)
    ir = np.stack([filt(noise(nir), sos('lowpass', 5200)) * np.exp(-tir / 0.42) for _ in range(2)], axis=1)
    ir[: int(0.018 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    irp = np.zeros((N, 2))
    irp[:nir] = ir
    wet = np.fft.irfft(np.fft.rfft(send, axis=0) * np.fft.rfft(irp, axis=0), n=N, axis=0)
    music += 0.55 * wet
    return circ_filt(music, sos('highpass', 30))


# ---------------------------------------------------------------- SFX
def sfx_thud():
    t = tt(int(0.6 * SR))
    f = 40 + 55 * np.exp(-t / 0.045)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.26)
    x += 0.35 * filt(noise(len(t)), sos('lowpass', 260)) * np.exp(-t / 0.03)
    return st(fade(x, 0.0008, 0.06))


def sfx_type(i, space=False):
    r = np.random.default_rng(1000 + i)                     # tiap huruf sedikit beda (amplitudo & pitch)
    t = tt(int(0.07 * SR))
    f = (2350 if not space else 1500) * r.uniform(0.93, 1.07)
    x = 0.5 * np.sin(2 * np.pi * f * t) * np.exp(-t / 0.010)
    x += 0.6 * filt(r.standard_normal(len(t)), sos('highpass', 1800)) * np.exp(-t / 0.0035)
    x += (0.45 if space else 0.25) * np.sin(2 * np.pi * (240 if space else 300) * r.uniform(0.95, 1.05) * t) * np.exp(-t / 0.018)
    return st(fade(x * r.uniform(0.75, 1.0), 0.0004, 0.012), r.uniform(-0.15, 0.15))


def sfx_whoosh():
    n = int(0.55 * SR)
    t = tt(n)
    env = np.where(t < 0.16, (t / 0.16) ** 0.6, np.exp(-(t - 0.16) / 0.12))
    x = noise(n)
    # filter bandpass yang menyapu 350 -> 2400 Hz (state-variable filter per sampel)
    fc = 350 * (2400 / 350) ** np.clip(t / 0.3, 0, 1)
    y = np.zeros(n)
    low = band = 0.0
    q = 0.7
    for k in range(n):
        g = 2 * np.sin(np.pi * fc[k] / SR)
        low += g * band
        high = x[k] - low - q * band
        band += g * high
        y[k] = band
    y *= env
    pan = np.linspace(-0.35, 0.35, n)
    out = np.stack([y * np.cos((pan + 1) * np.pi / 4), y * np.sin((pan + 1) * np.pi / 4)], axis=1)
    return fade(out, 0.0005, 0.04)


def sfx_click():
    t = tt(int(0.12 * SR))
    x = 0.5 * np.sin(2 * np.pi * 1500 * t) * np.exp(-t / 0.018)
    x += 0.45 * np.sin(2 * np.pi * 420 * t) * np.exp(-t / 0.028)
    x += 0.35 * filt(noise(len(t)), sos('highpass', 2500)) * np.exp(-t / 0.002)
    return st(fade(x, 0.0004, 0.02))


def sfx_tick():
    t = tt(int(0.16 * SR))
    f = 700 + 600 * np.clip(t / 0.03, 0, 1)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (np.sin(ph) + 0.25 * np.sin(2 * ph)) * np.exp(-t / 0.035)
    return st(fade(x, 0.0008, 0.02), 0.1)


def sfx_ding():
    t = tt(int(1.7 * SR))
    x = np.zeros(len(t))
    for f0, a0 in ((1046.5, 1.0), (783.99, 0.45)):          # C6 + G5: cocok dengan kunci F mayor
        for ratio, amp, dec in ((1, 1, 1.1), (2.0, 0.3, 0.5), (2.76, 0.16, 0.3), (5.4, 0.05, 0.12)):
            x += a0 * amp * np.sin(2 * np.pi * f0 * ratio * t) * np.exp(-t / dec)
    return st(fade(x * np.minimum(1, t / 0.002), 0.0005, 0.1), 0.05)


def sfx_swipe(dur=0.45):
    n = int((dur + 0.08) * SR)
    t = tt(n)
    x = filt(noise(n), sos('bandpass', [2200, 6500]))
    am = 1 + 0.35 * filt(noise(n), sos('lowpass', 35)) / 0.2
    env = np.minimum(1, t / 0.015) * np.where(t < dur, 1, np.exp(-(t - dur) / 0.03))
    y = x * np.clip(am, 0.3, 1.8) * env
    pan = np.linspace(-0.4, 0.4, n)                          # stabilo bergerak kiri -> kanan
    out = np.stack([y * np.cos((pan + 1) * np.pi / 4), y * np.sin((pan + 1) * np.pi / 4)], axis=1)
    return fade(out, 0.0005, 0.03)


def sfx_stamp():
    t = tt(int(0.4 * SR))
    x = np.sin(2 * np.pi * 95 * t) * np.exp(-t / 0.085)
    x += 0.5 * filt(noise(len(t)), sos('bandpass', [220, 1500])) * np.exp(-t / 0.028)
    x += 0.2 * filt(noise(len(t)), sos('highpass', 2200)) * np.exp(-t / 0.012)
    return st(fade(x, 0.0005, 0.04))


R4 = np.random.default_rng(404)


def bell(f, dec, t):
    x = np.sin(2 * np.pi * f * t) * np.exp(-t / dec)
    x += 0.28 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / (dec * 0.45))
    x += 0.08 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t / (dec * 0.25))
    return x * np.minimum(1, t / 0.003)


def sfx_note1():
    t = tt(int(0.6 * SR))
    return st(fade(bell(523.25, 0.16, t), 0.0005, 0.05), -0.1)          # C5, pendek


def sfx_note2():
    t = tt(int(2.2 * SR))
    return st(fade(bell(698.46, 0.9, t) + 0.35 * bell(1396.9, 0.4, t), 0.0005, 0.2), 0.1)   # F5 (tonika)


def sfx_press():
    """Klik lembut + 'pop' kecil (sinus naik 380 -> 820 Hz)."""
    t = tt(int(0.2 * SR))
    f = 380 + 440 * np.clip(t / 0.025, 0, 1)
    pop = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.05)
    clk = 0.5 * np.sin(2 * np.pi * 1300 * t) * np.exp(-t / 0.012) + 0.3 * filt(R4.standard_normal(len(t)), sos('highpass', 2500)) * np.exp(-t / 0.0018)
    return st(fade(0.8 * pop + clk, 0.0004, 0.03))


def sfx_plop():
    t = tt(int(0.22 * SR))
    f = 260 - 110 * np.clip(t / 0.06, 0, 1)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.07)
    x += 0.15 * filt(R4.standard_normal(len(t)), sos('lowpass', 900)) * np.exp(-t / 0.015)
    return st(fade(x, 0.0005, 0.03))


def norm_peak(x, db):
    return x / (np.abs(x).max() + 1e-12) * 10 ** (db / 20)


# level relatif (dBFS puncak sebelum master); dipilih agar SFX di atas musik tapi tidak menusuk
SFX = {
    'thud': (sfx_thud(), -5.0, 0.42),      # (bunyi, puncak dB, kedalaman ducking musik)
    'whoosh': (sfx_whoosh(), -19.0, 0.0),
    'click': (sfx_click(), -15.0, 0.18),
    'tick': (sfx_tick(), -17.0, 0.15),
    'ding': (sfx_ding(), -13.0, 0.3),
    'swipe': (sfx_swipe(), -20.0, 0.12),
    'stamp': (sfx_stamp(), -8.0, 0.38),
    'plop': (sfx_plop(), -19.0, 0.08),
    'note1': (sfx_note1(), -17.0, 0.0),
    'note2': (sfx_note2(), -14.0, 0.22),
    'press': (sfx_press(), -14.0, 0.25),
}
SFX = {k: (norm_peak(v, db), db, d) for k, (v, db, d) in SFX.items()}


def build_sfx():
    out = np.zeros((N, 2))
    duck = np.zeros(N)
    os.makedirs(os.path.join(DIR, 'sfx'), exist_ok=True)
    for k, (x, _, _) in SFX.items():
        wavfile.write(os.path.join(DIR, 'sfx', f'{k}.wav'), SR, x.astype(np.float32))
    for i in range(3):
        wavfile.write(os.path.join(DIR, 'sfx', f'type-{i + 1}.wav'), SR, norm_peak(sfx_type(i), -24).astype(np.float32))
    for e in EVENTS:
        t0 = e['t'] + SFX_SHIFT
        if e['type'] == 'type':
            x = norm_peak(sfx_type(e['i'], e.get('space', False)), -24 - (2 if e.get('space') else 0))
            depth = 0
        else:
            x, _, depth = SFX[e['type']]
            x = x * e.get('gain', 1)
        place(out, t0, x)
        if depth:
            # ducking halus: turun dalam 10 ms, tahan 60 ms, pulih 300 ms
            n = int(0.5 * SR)
            tt_ = tt(n)
            env = np.where(tt_ < 0.01, tt_ / 0.01, np.where(tt_ < 0.07, 1, np.exp(-(tt_ - 0.07) / 0.3)))
            d = np.zeros(N)
            place(d, t0 - 0.005, env * depth)
            duck = np.maximum(duck, d)
    return out, 1 - duck


# ---------------------------------------------------------------- loudness (ITU-R BS.1770) dan limiter
def lufs(x):
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, 0.73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1, -1.99004745483398, 0.99007225036621]
    y = signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=0), axis=0)
    blk, hop = int(0.4 * SR), int(0.1 * SR)
    ms = np.array([(y[i:i + blk] ** 2).mean(axis=0).sum() for i in range(0, len(y) - blk, hop)])
    lk = -0.691 + 10 * np.log10(ms + 1e-12)
    g = ms[lk > -70]
    rel = -0.691 + 10 * np.log10(g.mean()) - 10
    g2 = ms[(lk > -70) & (lk > rel)]
    return -0.691 + 10 * np.log10(g2.mean())


def true_peak_db(x):
    up = signal.resample_poly(np.concatenate([x[-256:], x, x[:256]]), 4, 1, axis=0)
    return 20 * np.log10(np.abs(up).max() + 1e-12)


def limiter(x, ceil_db=-1.3, look=0.003, rel=0.08):
    """Limiter look-ahead lembut, melingkar: gain = min(1, ambang/|x| teroversampel), dihaluskan."""
    thr = 10 ** (ceil_db / 20)
    up = np.abs(signal.resample_poly(x, 4, 1, axis=0)).max(axis=1)
    peak = up.reshape(-1, 4).max(axis=1)[:len(x)]
    need = np.minimum(1, thr / np.maximum(peak, 1e-9))
    w = int(look * SR)
    need = minimum_filter1d(need, size=w, mode='wrap', origin=-(w // 2))    # look-ahead: turun sebelum puncak
    g = np.empty_like(need)
    a = np.exp(-1 / (rel * SR))
    cur = 1.0
    for _ in range(2):                                                      # 2 putaran: keadaan tunak melingkar
        for i in range(len(need)):
            cur = need[i] if need[i] < cur else a * cur + (1 - a) * need[i]
            g[i] = cur
    return x * g[:, None], float(g.min())


def main():
    music = build_music()
    sfx, duck = build_sfx()
    # musik dinormalisasi ke -20 LUFS sebelum master (ruang untuk SFX)
    music *= 10 ** ((-20 - lufs(music)) / 20)
    os.makedirs(STEMS, exist_ok=True)
    os.makedirs(os.path.join(DIR, 'verify'), exist_ok=True)
    wavfile.write(os.path.join(STEMS, 'music.wav'), SR, music.astype(np.float32))
    wavfile.write(os.path.join(STEMS, 'sfx.wav'), SR, sfx.astype(np.float32))
    mix = music * duck[:, None] + sfx
    mix = circ_filt(mix, sos('highpass', 30))
    # master: gain linear terukur ke -14 LUFS, limiter hanya jika true peak > -1 dBTP
    info = {'premaster_lufs': lufs(mix)}
    mix *= 10 ** ((-14 - info['premaster_lufs']) / 20)
    info['tp_before_limit'] = true_peak_db(mix)
    gmin = 1.0
    for _ in range(3):
        if true_peak_db(mix) <= -1.2:
            break
        mix, gmin = limiter(mix)
        mix *= 10 ** ((-14 - lufs(mix)) / 20)
    # fade 80 ms di awal dan 120 ms di akhir (pemutaran pertama / akhir berkas); musiknya sendiri melingkar
    fi, fo = int(0.08 * SR), int(0.12 * SR)
    mix[:fi] *= (np.sin(np.linspace(0, np.pi / 2, fi)) ** 2)[:, None]
    mix[-fo:] *= (np.cos(np.linspace(0, np.pi / 2, fo)) ** 2)[:, None]
    info.update(final_lufs_internal=lufs(mix), final_true_peak_internal=true_peak_db(mix),
                limiter_min_gain_db=20 * np.log10(gmin), samples=len(mix), seconds=len(mix) / SR,
                sample_peak=float(np.abs(mix).max()))
    assert np.abs(mix).max() < 1.0, 'clipping!'
    wavfile.write(os.path.join(DIR, 'soundtrack.wav'), SR, mix.astype(np.float32))
    json.dump(info, open(os.path.join(DIR, 'verify', 'loudness-internal.json'), 'w'), indent=1)
    print(json.dumps(info, indent=1))


if __name__ == '__main__':
    main()
