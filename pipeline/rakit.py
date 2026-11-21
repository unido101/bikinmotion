"""Merakit MP4 final: video bisu + VO (+ musik opsional dengan ducking), lalu pengecekan teknis.
Lintas platform (Windows, macOS, Linux): hanya memerlukan ffmpeg dan ffprobe di PATH, tanpa bash.

Durasi akhir = durasi VO + ekor. VO tidak dipotong atau dipercepat.
"""
import json
import re
import subprocess


def _jalan(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def durasi(path):
    p = _jalan(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe gagal membaca {path}: {p.stderr.strip()[:200]}")
    return float(p.stdout.strip())


def rakit(video, vo, keluar, musik=None, ekor=0.5, ulang_encode=False):
    """Return (ok, laporan) dengan laporan = [(nama, lolos, detail)]."""
    vo_dur = durasi(vo)
    total = round(vo_dur + ekor, 3)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(video), "-i", str(vo)]
    if musik:
        fade = max(0.0, total - 1.5)
        cmd += ["-stream_loop", "-1", "-i", str(musik)]
        graf = (
            f"[1:a]apad=pad_dur={ekor},aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[vo][vosc];"
            f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.35,atrim=0:{total},"
            f"afade=t=out:st={fade}:d=1.5[m];"
            "[m][vosc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[md];"
            "[vo][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]"
        )
    else:
        graf = (f"[1:a]apad=pad_dur={ekor},aformat=sample_rates=48000:channel_layouts=stereo,"
                "alimiter=limit=0.95[a]")
    vcodec = (["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30"]
              if ulang_encode else ["-c:v", "copy"])   # video bisu dari renderer sudah H.264 yuv420p 30 fps
    cmd += ["-filter_complex", graf, "-map", "0:v", "-map", "[a]", *vcodec,
            "-c:a", "aac", "-b:a", "192k", "-t", str(total), "-movflags", "+faststart", str(keluar)]
    p = _jalan(cmd)
    if p.returncode != 0:
        return False, [("ffmpeg merakit audio dan video", False, p.stderr.strip()[-300:])]
    return _cek(keluar, vo_dur, total)


def _cek(keluar, vo_dur, total):
    p = _jalan(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(keluar)])
    info = json.loads(p.stdout)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    laporan = []

    def cek(nama, ok, detail=""):
        laporan.append((nama, bool(ok), detail))

    num, den = (int(x) for x in v["avg_frame_rate"].split("/"))
    fps = num / den
    cek("30 fps", abs(fps - 30) < 0.01, f"{fps:.3f}")
    cek("codec H.264", v["codec_name"] == "h264", v["codec_name"])
    cek("pixel format yuv420p", v["pix_fmt"] == "yuv420p", v["pix_fmt"])
    cek("ada audio", a is not None, a["codec_name"] if a else "tidak ada")
    vd = float(v.get("duration") or info["format"]["duration"])
    ad = float(a["duration"]) if a else 0.0
    cek("durasi video = VO + ekor", abs(vd - total) < 0.1, f"video {vd:.2f}s, target {total:.2f}s")
    cek("selisih audio-video < 0,1 s", abs(vd - ad) < 0.1, f"audio {ad:.2f}s")
    cek("VO tidak terpotong", ad >= vo_dur - 0.05, f"audio {ad:.2f}s, VO {vo_dur:.2f}s")
    vol = _jalan(["ffmpeg", "-hide_banner", "-i", str(keluar), "-af", "volumedetect", "-vn", "-f", "null", "-"])
    m = re.search(r"max_volume: (-?[\d.]+) dB", vol.stderr)
    if m:
        cek("tidak ada audio pecah (puncak di bawah 0 dB)", float(m.group(1)) < 0.0, f"puncak {m.group(1)} dB")
    cek("resolusi", True, f"{v['width']}x{v['height']}")
    return all(ok for _, ok, _ in laporan), laporan
