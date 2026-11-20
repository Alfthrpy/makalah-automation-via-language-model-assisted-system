#!/usr/bin/env bash
# Bangun ulang video promo MALAS v3 dari nol (tanpa internet):
#   1) render video bisu per bingkai + events.json      (render.cjs, Playwright + ffmpeg)
#   2) sintesis soundtrack + SFX dari events.json         (audio.py, numpy/scipy)
#   3) mux -> malas-promo-v3.mp4 (H.264 + AAC 192 kbps 48 kHz stereo)
#   4) verifikasi audio: loudness, clipping, sinkron, gambar (verify_audio.py + ffmpeg)
# Jalankan: bash marketing/video/v3/build.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PY=(uv run --no-project --with numpy --with scipy --with pillow python -I)

NODE_PATH="$(npm root -g)" node "$DIR/render.cjs"
"${PY[@]}" "$DIR/audio.py" "$DIR"
ffmpeg -v error -y -i "$DIR/malas-promo-v3-silent.mp4" -i "$DIR/soundtrack.wav" \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart \
  "$DIR/malas-promo-v3.mp4"
"${PY[@]}" "$DIR/verify_audio.py" "$DIR"

echo "--- ffprobe"
ffprobe -v error -show_entries stream=index,codec_name,width,height,r_frame_rate,sample_rate,channels,bit_rate,duration:format=duration,size \
  -of compact "$DIR/malas-promo-v3.mp4"
echo "--- ebur128 (soundtrack.wav)"
ffmpeg -hide_banner -nostats -i "$DIR/soundtrack.wav" -af ebur128=peak=true:framelog=quiet -f null - 2>&1 | grep -E "^ +(I|LRA|Peak):"
echo "--- ebur128 (audio di dalam mp4, setelah AAC)"
ffmpeg -hide_banner -nostats -i "$DIR/malas-promo-v3.mp4" -map 0:a -af ebur128=peak=true:framelog=quiet -f null - 2>&1 | grep -E "^ +(I|LRA|Peak):"
echo "--- astats (soundtrack.wav)"
ffmpeg -hide_banner -nostats -i "$DIR/soundtrack.wav" -af astats=measure_perchannel=none -f null - 2>&1 | grep -E "Peak level|RMS level|DC offset"
echo "--- jumlah sampel clip (|x| >= 1.0) dan offset AAC vs WAV"
"${PY[@]}" "$DIR/check_mux.py" "$DIR"
