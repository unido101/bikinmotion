#!/usr/bin/env bash
# Merakit MP4 final: video bisu + VO (+ musik opsional dengan ducking), lalu cek dasar.
# Pemakaian:
#   bash scripts/rakit_mp4.sh VIDEO_BISU.mp4 VO.(mp3|wav|m4a) OUTPUT.mp4 [MUSIK.mp3] [EKOR_DETIK=0.5]
# Durasi akhir = durasi VO + ekor. VO tidak dipotong atau dipercepat.
set -euo pipefail

# Video bisu dari renderer sudah H.264 yuv420p 30 fps, jadi disalin tanpa encode ulang.
# Set RAKIT_REENCODE=1 bila video bisu berasal dari sumber lain.
if [[ "${RAKIT_REENCODE:-0}" == "1" ]]; then VCODEC=(-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30); else VCODEC=(-c:v copy); fi

VIDEO="${1:?video bisu}"; VO="${2:?file VO}"; OUT="${3:?output mp4}"
MUSIK="${4:-}"; EKOR="${5:-0.5}"

dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }
VO_DUR=$(dur "$VO")
TOTAL=$(python3 -c "print(round($VO_DUR + $EKOR, 3))")
echo "Durasi VO: $VO_DUR  | Total video: $TOTAL"

if [[ -n "$MUSIK" ]]; then
  FADE_ST=$(python3 -c "print(max(0,$TOTAL-1.5))")
  ffmpeg -y -hide_banner -loglevel error \
    -i "$VIDEO" -i "$VO" -stream_loop -1 -i "$MUSIK" \
    -filter_complex "\
[1:a]apad=pad_dur=${EKOR},aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[vo][vosc];\
[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.35,atrim=0:${TOTAL},afade=t=out:st=${FADE_ST}:d=1.5[m];\
[m][vosc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];\
[vo][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]" \
    -map 0:v -map "[a]" \
    "${VCODEC[@]}" \
    -c:a aac -b:a 192k -t "$TOTAL" -movflags +faststart "$OUT"
else
  ffmpeg -y -hide_banner -loglevel error \
    -i "$VIDEO" -i "$VO" \
    -filter_complex "[1:a]apad=pad_dur=${EKOR},aformat=sample_rates=48000:channel_layouts=stereo,alimiter=limit=0.95[a]" \
    -map 0:v -map "[a]" \
    "${VCODEC[@]}" \
    -c:a aac -b:a 192k -t "$TOTAL" -movflags +faststart "$OUT"
fi

echo; echo "== Pengecekan =="
python3 - "$OUT" "$VO_DUR" "$TOTAL" <<'PY'
import json, subprocess, sys
out, vo_dur, total = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
p = subprocess.run(["ffprobe","-v","error","-print_format","json","-show_streams","-show_format",out],
                   capture_output=True, text=True, check=True)
info = json.loads(p.stdout)
v = next((s for s in info["streams"] if s["codec_type"]=="video"), None)
a = next((s for s in info["streams"] if s["codec_type"]=="audio"), None)
ok = True
def cek(nama, kondisi, detail=""):
    global ok
    print(("LOLOS  " if kondisi else "GAGAL  ") + nama + (f"  ({detail})" if detail else ""))
    ok = ok and kondisi
num, den = map(int, v["avg_frame_rate"].split("/"))
fps = num/den
cek("30 fps", abs(fps-30) < 0.01, f"{fps:.3f}")
cek("codec H.264", v["codec_name"]=="h264", v["codec_name"])
cek("pixel format yuv420p", v["pix_fmt"]=="yuv420p", v["pix_fmt"])
cek("ada audio", a is not None, a["codec_name"] if a else "tidak ada")
vd = float(v.get("duration") or info["format"]["duration"])
ad = float(a["duration"]) if a else 0
cek("durasi video ~ VO + ekor", abs(vd-total) < 0.1, f"video {vd:.2f}s, target {total:.2f}s")
cek("selisih audio-video < 0,1 s", abs(vd-ad) < 0.1, f"audio {ad:.2f}s")
cek("VO tidak terpotong", ad >= vo_dur - 0.05, f"audio {ad:.2f}s, VO {vo_dur:.2f}s")
print(f"Resolusi: {v['width']}x{v['height']}")
sys.exit(0 if ok else 1)
PY

echo; echo "== Level audio =="
ffmpeg -hide_banner -i "$OUT" -af volumedetect -vn -f null - 2>&1 | grep -E "mean_volume|max_volume" || true
echo "Catatan: max_volume harus di bawah 0.0 dB. Lanjutkan dengan cek visual lewat ekstraksi frame:"
echo "  ffmpeg -ss DETIK -i $OUT -frames:v 1 frame_DETIK.png"
