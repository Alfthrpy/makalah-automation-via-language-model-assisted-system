#!/usr/bin/env python3
"""Soundtrack orisinal MALAS promo v6 ("5 Tahap Duka Ngerjain Makalah"): musik + SFX, disintesis lokal
(tanpa sampel, tanpa internet). Pipeline sama dengan v4/v5; aransemennya baru dan berbab (satu warna per tahap).

Jalankan (lewat build.sh, atau langsung):
    uv run --no-project --with numpy --with scipy python -I audio.py <folder-v6>

Masukan : <folder-v6>/events.json  (ditulis render.cjs dari window.TIMELINE + window.EVENTS di index.html)
Keluaran: soundtrack.wav (master, 48 kHz stereo float32), sfx/*.wav (tiap SFX satu berkas),
          $STEMS_DIR/{music,sfx}.wav (stem analisis; default di luar repo), verify/loudness-internal.json

Desain singkat
- Tempo 96 BPM, 4/4 lurus, 120 ketukan = 75,0 dtk = 30 bar = panjang video. Kunci D mayor.
- Satu warna musik per adegan (batas adegan jatuh di garis bar): hook (tipis) | T1 Ngeles santai | T2 Kesal minor tegang |
  T3 Nawar jenaka (arpeggio satu oktaf lebih tinggi, rim + hat) | T4 Pasrah hampir sunyi (tanpa drum, nada jarang;
  komedi lewat jeda) | T5 Nerima terang & membangun | TR "tercapai" (akor tonika + SFX tada) | CTA penuh,
  napas satu ketukan sebelum punchline "MALAS." (record scratch), napas setengah ketukan sebelum tombol, lalu akor mendarat.
- Instrumen: arpeggio "marimba" sintetis, pad harmonik ber-low-pass, bas sinus, kick/snare/rim/hat sintetis,
  reverb = konvolusi derau meluruh. Musik dirender MELINGKAR; SFX ditempatkan sampel-akurat pada waktu
  peristiwa + 1/2 bingkai. Master -14 LUFS terintegrasi, true peak <= -1 dBTP, tanpa clipping.
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
N = FRAMES * SR // FPS                      # sampel = durasi video persis (900 bingkai -> 1.440.000 sampel)
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
def marimba(f, vel, pan=0.0):
    """Ketukan bilah: sinus + parsial 4x dan 9,2x yang cepat meluruh, peluruhan utama ~0,3 dtk."""
    t = tt(int(1.1 * SR))
    x = np.sin(2 * np.pi * f * t)
    x += 0.25 * np.sin(2 * np.pi * 4.0 * f * t) * np.exp(-t / 0.06)
    x += 0.08 * np.sin(2 * np.pi * 9.2 * f * t) * np.exp(-t / 0.02)
    env = np.minimum(1, t / 0.002) * np.exp(-t / 0.3)
    return st(fade(filt(x * env * vel, sos('lowpass', 6000)), 0.0005, 0.05), pan)


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
DMAJ9, BM7, GMAJ7, ASUS = ([57, 61, 64, 66], 38), ([57, 59, 62, 66], 35), ([55, 59, 62, 66], 43), ([55, 57, 62, 64], 45)
EM7, A7, FSM7 = ([55, 59, 62, 64], 40), ([55, 57, 61, 64], 45), ([57, 61, 64, 66], 42)
CHORDS = [
    DMAJ9,                              # bar 0   : hook
    DMAJ9, GMAJ7, BM7, ASUS, DMAJ9,     # bar 1-5 : T1 Ngeles (santai, mayor)
    BM7, EM7, FSM7, A7,                 # bar 6-9 : T2 Kesal (minor, tegang)
    GMAJ7, A7, DMAJ9, BM7,              # bar 10-13: T3 Nawar (jenaka)
    BM7, GMAJ7, BM7, GMAJ7, EM7,        # bar 14-18: T4 Pasrah (melambat, hampir sunyi)
    GMAJ7, ASUS, BM7, EM7, GMAJ7, A7,   # bar 19-24: T5 Nerima (terang, membangun)
    DMAJ9,                              # bar 25  : tercapai (tonika, SFX tada)
    GMAJ7, ASUS,                        # bar 26-27: CTA-a (punchline nama)
    EM7,                                # bar 28  : CTA-b menuju tombol
    DMAJ9,                              # bar 29  : mendarat tepat saat tombol ditekan
]
assert len(CHORDS) == 30
BAR = 4 * BEAT
ARP = [0, 2, 4, 3, 1, 3, 2, 4]   # indeks ke [voicing + oktaf akar], per seperdelapan


def section(t):
    """Intensitas per kelompok instrumen menurut adegan (waktu dari index.html)."""
    if t < SC['T1']:
        return dict(kick=0, snare=0, rim=0, hat=0.35, arp=0.7, bass=0.8, pad=1.0)                 # hook
    if t < SC['T2']:
        return dict(kick=0.6, snare=0, rim=0.55, hat=0.6, arp=0.85, bass=1.0, pad=0.9)            # T1 Ngeles: santai
    if t < SC['T3']:
        return dict(kick=0.8, snare=0.7, rim=0, hat=0.5, arp=0.55, bass=1.0, pad=1.0)             # T2 Kesal: tegang
    if t < SC['T4']:
        return dict(kick=0.5, snare=0, rim=0.7, hat=0.8, arp=1.0, bass=0.9, pad=0.6, up=12)       # T3 Nawar: jenaka
    if t < SC['T5']:
        return dict(kick=0, snare=0, rim=0, hat=0, arp=0.5, bass=0.55, pad=0.7, sparse=True)      # T4 Pasrah: nyaris sunyi
    if t < SC['T5'] + 4 * BEAT:
        return dict(kick=0.5, snare=0, rim=0.4, hat=0.6, arp=0.85, bass=0.9, pad=0.9)             # T5 Nerima: mulai terang
    if t < SC['TR']:
        return dict(kick=1, snare=1, rim=0, hat=1, arp=1, bass=1, pad=0.8)                        # T5 Nerima: membangun
    if t < SC['CA']:
        return dict(kick=1, snare=0.8, rim=0, hat=1, arp=1, bass=1, pad=1.0)                      # tercapai
    if SC['CA'] + 3 * BEAT <= t < SC['CA'] + 4 * BEAT:
        return dict(kick=0, snare=0, rim=0, hat=0, arp=0, bass=0.7, pad=1.0)                      # napas sebelum "MALAS."
    if t < PRESS - 0.5 * BEAT:
        return dict(kick=1, snare=1, rim=0, hat=1, arp=1, bass=1, pad=0.8)                        # CTA
    if t < PRESS:
        return dict(kick=0, snare=0, rim=0, hat=0, arp=0, bass=0.7, pad=1.0)                      # napas sebelum tekan
    return dict(kick=0, snare=0, rim=0, hat=0.3, arp=0.55, bass=0.8, pad=1.0)                     # mendarat, meluruh


def humanize(ms=5):
    return rng.uniform(-ms, ms) / 1000


def build_music():
    dry = np.zeros((N, 2))
    send = np.zeros((N, 2))
    drums = np.zeros((N, 2))
    for bi, (voic, bnote) in enumerate(CHORDS):
        b0 = bi * BAR
        last = bi == len(CHORDS) - 1
        p = pad([mtof(m) for m in voic], BAR) * 0.10 * section(b0 + 0.01)['pad']
        place(dry, b0, p * 0.7)
        place(send, b0, p * 0.6)
        # arpeggio seperdelapan
        notes = sorted(voic) + [sorted(voic)[0] + 12]
        for k in range(8):
            t0 = b0 + k * 0.5 * BEAT
            sec_ = section(t0 + 0.001)
            g = sec_['arp']
            if not g or (last and k >= 4) or (sec_.get('sparse') and k not in (0, 4)):
                continue
            vel = (0.9 if k % 2 == 0 else 0.62) * g * rng.uniform(0.9, 1.0)
            x = marimba(mtof(notes[ARP[k]] + 12 + sec_.get('up', 0)), vel, pan=0.25 if k % 2 else -0.25) * 0.10
            place(dry, t0 + humanize(3), x)
            place(send, t0, x * 0.6)
        # bas: akar di 1, kuint sebelum 3, akar di 3 (bar akhir: satu nada panjang)
        bpat = [(0.0, 1.4, 1.0), (1.5, 0.4, 0.6), (2.0, 1.4, 0.85), (3.5, 0.4, 0.55)]
        if b0 < SC['T1'] or section(b0 + 0.01).get('sparse') or last:
            bpat = [(0.0, 3.7, 0.9)]
        for pos, dur, vel in bpat:
            t0 = b0 + pos * BEAT
            f = mtof(bnote + (7 if pos in (1.5, 3.5) else 0))
            place(dry, t0, st(bass(f, dur * BEAT, vel * section(t0 + 0.01)['bass']) * 0.34))
        # drum lurus
        for k in range(8):
            t0 = b0 + k * 0.5 * BEAT
            s = section(t0 + 0.001)
            if k in (0, 4) and s['kick']:
                place(drums, t0, st(kick(s['kick'] * (1 if k == 0 else 0.8)) * 0.55))
            if k == 5 and s['kick'] and s['snare']:
                place(drums, t0, st(kick(0.5 * s['kick']) * 0.55))
            if k in (2, 6) and s['snare']:
                x = st(snare(s['snare'] * (0.9 if k == 2 else 1.0)) * 0.2, 0.08)
                place(drums, t0 + humanize(3), x)
                place(send, t0, x * 0.35)
            if k in (2, 6) and s['rim']:
                x = st(rim(s['rim']) * 0.12, 0.1)
                place(drums, t0 + humanize(3), x)
                place(send, t0, x * 0.5)
            if s['hat']:
                v = (0.55 if k % 2 == 0 else 0.4) * s['hat'] * rng.uniform(0.85, 1.0)
                place(drums, t0 + humanize(4), st(hat(v) * 0.05, -0.25))
    place(drums, PRESS, st(kick(0.75) * 0.55))       # kick lembut tepat di momen tekan
    music = dry + drums
    nir = int(1.7 * SR)
    tir = tt(nir)
    ir = np.stack([filt(noise(nir), sos('lowpass', 5600)) * np.exp(-tir / 0.38) for _ in range(2)], axis=1)
    ir[: int(0.015 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    irp = np.zeros((N, 2))
    irp[:nir] = ir
    wet = np.fft.irfft(np.fft.rfft(send, axis=0) * np.fft.rfft(irp, axis=0), n=N, axis=0)
    music += 0.5 * wet
    return circ_filt(music, sos('highpass', 30))


# ---------------------------------------------------------------- SFX
def sfx_thud():
    t = tt(int(0.6 * SR))
    f = 40 + 55 * np.exp(-t / 0.045)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.26)
    x += 0.35 * filt(noise(len(t)), sos('lowpass', 260)) * np.exp(-t / 0.03)
    return st(fade(x, 0.0008, 0.06))


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
    for f0, a0 in ((1174.66, 1.0), (880.0, 0.45)):          # D6 + A5: cocok dengan kunci D mayor
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
    return st(fade(bell(440.0, 0.16, t), 0.0005, 0.05), -0.1)           # A4 (dominan), pendek


def sfx_note2():
    t = tt(int(2.2 * SR))
    return st(fade(bell(587.33, 0.9, t) + 0.35 * bell(1174.66, 0.4, t), 0.0005, 0.2), 0.1)  # D5 (tonika)


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


def sfx_pop():
    """'Pop' gelembung untuk kartu/statistik yang masuk: sinus turun 950 -> 520 Hz + klik halus."""
    t = tt(int(0.16 * SR))
    f = 520 + 430 * np.exp(-t / 0.018)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.045)
    x += 0.2 * filt(R4.standard_normal(len(t)), sos('highpass', 3000)) * np.exp(-t / 0.0015)
    return st(fade(x, 0.0004, 0.03), 0.1)


BLIP_NOTES = [74, 76, 78, 81, 83, 86, 88, 90]   # D5 E5 F#5 A5 B5 D6 E6 F#6 (pentatonik D, naik per chip topik)


def sfx_blip(i):
    t = tt(int(0.14 * SR))
    f = mtof(BLIP_NOTES[i % len(BLIP_NOTES)])
    x = (np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)) * np.exp(-t / 0.045) * np.minimum(1, t / 0.002)
    return st(fade(x, 0.0004, 0.03), -0.3 + 0.6 * (i % 8) / 7)


def sfx_notif():
    """Notifikasi chat: dua bunyi lonceng G6 -> D7 pendek."""
    t = tt(int(1.0 * SR))
    y = bell(1567.98, 0.2, t) * 0.8
    d = int(0.11 * SR)
    y[d:] += bell(2349.32, 0.26, t[:len(t) - d])
    return st(fade(y, 0.0005, 0.12), 0.05)


def sfx_sent():
    """Pesan terkirim: sinus naik 520 -> 880 Hz, cepat meluruh + klik halus."""
    t = tt(int(0.18 * SR))
    f = 520 + 360 * np.clip(t / 0.05, 0, 1)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.05)
    x += 0.15 * filt(R4.standard_normal(len(t)), sos('highpass', 3500)) * np.exp(-t / 0.002)
    return st(fade(x, 0.0004, 0.03), 0.15)


def sfx_recv():
    """Pesan diterima: sinus turun 760 -> 430 Hz, lebih lembut dari 'sent'."""
    t = tt(int(0.2 * SR))
    f = 430 + 330 * np.exp(-t / 0.03)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.07)
    return st(fade(x, 0.0004, 0.03), -0.15)


def sfx_ting():
    """Dokumen dibuka: 'ting' lonceng kecil cerah (G6 + D7)."""
    t = tt(int(0.7 * SR))
    x = bell(1567.98, 0.16, t) + 0.5 * bell(2349.32, 0.1, t)
    return st(fade(x, 0.0004, 0.08), 0.1)


def sfx_scratch():
    """Record scratch: derau + gergaji dengan frekuensi menyapu naik lalu turun, ~0,38 dtk."""
    n = int(0.42 * SR)
    t = tt(n)
    f = np.where(t < 0.13, 150 + 1500 * (t / 0.13) ** 1.5,
                 np.where(t < 0.28, 1650 - 1450 * ((t - 0.13) / 0.15), 200))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = 0.6 * signal.sawtooth(ph) + 0.5 * R4.standard_normal(n)
    x = filt(x, sos('bandpass', [700, 5200]))
    env = np.minimum(1, t / 0.01) * np.where(t < 0.3, 1, np.exp(-(t - 0.3) / 0.025))
    env *= 0.75 + 0.25 * np.sin(2 * np.pi * 22 * t)          # getaran piringan hitam
    pan = np.linspace(-0.3, 0.3, n)
    y = x * env
    return fade(np.stack([y * np.cos((pan + 1) * np.pi / 4), y * np.sin((pan + 1) * np.pi / 4)], axis=1), 0.0005, 0.03)


def sfx_tada():
    """'Tercapai': arpeggio D5 F#5 A5 D6 berkilau + akor D mayor yang melebar, ~1,8 dtk."""
    n = int(1.9 * SR)
    t = tt(n)
    x = np.zeros(n)
    for k, m in enumerate((74, 78, 81, 86)):
        d = int(k * 0.07 * SR)
        x[d:] += bell(mtof(m), 0.5, t[:n - d]) * (0.7 + 0.1 * k)
    d = int(0.28 * SR)
    for m in (74, 78, 81):
        x[d:] += 0.35 * bell(mtof(m + 12), 0.9, t[:n - d])
    sp = filt(R4.standard_normal(n), sos('highpass', 6000)) * np.exp(-t / 0.5) * 0.05   # kilau
    return st(fade(x + sp, 0.0005, 0.2), 0.0)


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
    'pop': (sfx_pop(), -17.0, 0.1),
    'notif': (sfx_notif(), -14.0, 0.15),
    'sent': (sfx_sent(), -17.0, 0.05),
    'recv': (sfx_recv(), -17.0, 0.05),
    'ting': (sfx_ting(), -15.0, 0.1),
    'scratch': (sfx_scratch(), -10.0, 0.5),
    'tada': (sfx_tada(), -11.0, 0.3),
}
SFX = {k: (norm_peak(v, db), db, d) for k, (v, db, d) in SFX.items()}


def build_sfx():
    out = np.zeros((N, 2))
    duck = np.zeros(N)
    os.makedirs(os.path.join(DIR, 'sfx'), exist_ok=True)
    for k, (x, _, _) in SFX.items():
        wavfile.write(os.path.join(DIR, 'sfx', f'{k}.wav'), SR, x.astype(np.float32))
    for i in range(len(BLIP_NOTES)):
        wavfile.write(os.path.join(DIR, 'sfx', f'blip-{i + 1}.wav'), SR, norm_peak(sfx_blip(i), -21).astype(np.float32))
    for e in EVENTS:
        t0 = e['t'] + SFX_SHIFT
        if e['type'] == 'type':
            x = norm_peak(sfx_type(e['i'], e.get('space', False)), -24 - (2 if e.get('space') else 0))
            depth = 0
        elif e['type'] == 'blip':
            x = norm_peak(sfx_blip(e['i']), -21)
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
