#!/usr/bin/env python3
"""SilenceCut: cut the silence out of talking videos, add pro captions.

Pipeline: ffmpeg silencedetect -> keep the speech (with padding) ->
optional faster-whisper captions (word timing) -> burn captions in
with one of 112 caption templates (ASS/libass). No API key.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-show_entries", "stream=width,height", "-of", "json", path])
    d = json.loads(r.stdout)
    w = h = 0
    for s in d.get("streams", []):
        if s.get("width"):
            w, h = s["width"], s["height"]
    return float(d["format"]["duration"]), w, h


def detect_silences(path, thresh_db=-35, min_dur=0.55):
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-af",
             f"silencedetect=noise={thresh_db}dB:d={min_dur}", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(starts, ends))


def keep_segments(duration, silences, pad=0.12):
    keeps, cur = [], 0.0
    for s, e in silences:
        ks, ke = max(0.0, s + 0 - pad * 0), min(duration, e)
        seg_end = min(duration, s + pad)
        if seg_end - cur >= 0.12:
            keeps.append((cur, seg_end))
        cur = max(cur, min(duration, e - pad))
    if duration - cur >= 0.12:
        keeps.append((cur, duration))
    merged = []
    for a, b in keeps:
        if merged and a <= merged[-1][1] + 0.05:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


QUALITY = {"fast": ("22", "veryfast"), "balanced": ("18", "veryfast"), "best": ("15", "medium")}


def cut_video(src, keeps, out, quality="balanced"):
    fc = []
    for i, (a, b) in enumerate(keeps):
        fc.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        fc.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
    fc.append("".join(f"[v{i}][a{i}]" for i in range(len(keeps))) +
              f"concat=n={len(keeps)}:v=1:a=1[outv][outa]")
    crf, preset = QUALITY.get(quality, QUALITY["balanced"])
    r = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src,
             "-filter_complex", ";".join(fc), "-map", "[outv]", "-map", "[outa]",
             "-c:v", "libx264", "-crf", crf, "-preset", preset,
             "-c:a", "aac", "-b:a", "160k", out])
    if r.returncode != 0:
        raise RuntimeError("cut failed: " + r.stderr[-400:])


def find_stt_python():
    cands = [os.environ.get("SILENCECUT_STT_PYTHON", ""),
             os.path.expanduser("~/workspace/reel_skills/stt-venv/bin/python"),
             os.path.join(HERE, ".venv", "bin", "python"),
             os.path.join(HERE, ".venv", "Scripts", "python.exe"),
             sys.executable]
    for c in cands:
        if c and os.path.exists(c):
            r = run([c, "-c", "import faster_whisper"])
            if r.returncode == 0:
                return c
    return None


def transcribe(video, model="base", lang="auto", workdir=None):
    py = find_stt_python()
    if not py:
        raise RuntimeError("Captions need faster-whisper. Install: pip install faster-whisper (one time).")
    workdir = workdir or os.path.dirname(os.path.abspath(video))
    wav = os.path.join(workdir, "_sc_audio.wav")
    outj = os.path.join(workdir, "_sc_words.json")
    r = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video,
             "-vn", "-ac", "1", "-ar", "16000", wav])
    if r.returncode != 0:
        raise RuntimeError("audio extract failed")
    r = run([py, os.path.join(HERE, "transcribe.py"), wav, model, lang, outj])
    if r.returncode != 0:
        raise RuntimeError("transcribe failed: " + (r.stderr or r.stdout)[-400:])
    return json.load(open(outj))


def ass_color(hexs):
    h = hexs.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def t_ass(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs % 6000 / 100:.2f}"


def make_ass(data, tpl, width, height, main_override="", high_override=""):
    main = main_override.lstrip("#") or tpl["main"]
    high = high_override.lstrip("#") or tpl["highlight"]
    size = max(24, int(height * 0.052 * tpl.get("scale", 1.0)))
    align = {"bottom": 2, "middle": 5, "top": 8, "bottom-left": 1}[tpl["pos"]]
    mv = int(height * (0.05 if tpl["pos"] != "middle" else 0))
    if tpl.get("box"):
        border_style = 3
        back = "&H28" + ass_color(high)[4:]
        outline_col = "&H28" + ass_color(high)[4:]
    elif tpl.get("band"):
        border_style = 3
        back = "&H8C000000"
        outline_col = "&H8C000000"
    else:
        border_style = 1
        back = "&H00000000"
        outline_col = ass_color(tpl["outline_color"])
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{tpl['font']},{size},{ass_color(main)},{ass_color(high)},{outline_col},{back},{-1 if tpl['bold'] else 0},{-1 if tpl.get('italic') else 0},0,0,100,100,0,0,{border_style},{tpl['outline']},{tpl['shadow']},{align},40,40,{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for seg in data["segments"]:
        words = seg["words"] or [{"start": seg["start"], "end": seg["end"], "word": w}
                                  for w in seg["text"].split()]
        if not words:
            continue
        def txt(ws):
            s = " ".join(w["word"] for w in ws)
            return s.upper() if tpl["upper"] else s
        if tpl["anim"] == "karaoke":
            parts, prev = [], seg["start"]
            for w in words:
                d = max(1, int(round((w["end"] - prev) * 100)))
                parts.append(f"{{\\kf{d}}}{w['word']}")
                prev = w["end"]
            body = " ".join(parts)
            if tpl["upper"]:
                body = body.upper().replace("\\KF", "\\kf")
            ev.append(f"Dialogue: 0,{t_ass(seg['start'])},{t_ass(seg['end'])},Main,,0,0,0,,{body}")
        elif tpl["anim"] == "highlight":
            for i, w in enumerate(words):
                line = []
                for j, w2 in enumerate(words):
                    if j == i:
                        big = int(size * 1.3)
                        line.append(f"{{\\c{ass_color(high)}\\b1\\fs{big}}}{w2['word']}{{\\c{ass_color(main)}\\fs{size}}}")
                    else:
                        line.append(w2["word"])
                body = " ".join(line)
                if tpl["upper"]:
                    body = body.upper()
                ev.append(f"Dialogue: 0,{t_ass(w['start'])},{t_ass(w['end'])},Main,,0,0,0,,{body}")
        else:
            prefix = "{\\fad(120,120)}" if tpl["anim"] == "fade" else ""
            body_txt = txt(words)
            if tpl.get("stack"):
                ws = body_txt.split()
                half = (len(ws) + 1) // 2
                body_txt = " ".join(ws[:half]) + "\\N" + " ".join(ws[half:])
            ev.append(f"Dialogue: 0,{t_ass(seg['start'])},{t_ass(seg['end'])},Main,,0,0,0,,{prefix}{body_txt}")
    return head + "\n".join(ev) + "\n"


def load_templates():
    return json.load(open(os.path.join(HERE, "templates.json")))


def process(src, out, thresh=-35, min_dur=0.55, pad=0.12, captions=True,
            template_id="amber-karaoke", lang="auto", model="base",
            main_color="", high_color="", log=print, quality="balanced"):
    duration, w, h = probe(src)
    log(f"Video: {duration:.1f}s, {w}x{h}")
    sil = detect_silences(src, thresh, min_dur)
    keeps = keep_segments(duration, sil, pad)
    kept = sum(b - a for a, b in keeps)
    log(f"Silences found: {len(sil)} | keeping {len(keeps)} speech parts | {duration:.1f}s -> {kept:.1f}s (saves {duration - kept:.1f}s)")
    tmp = out + ".cut.mp4"
    cut_video(src, keeps, tmp, quality)
    if not captions:
        os.replace(tmp, out)
        return {"out": out, "before": duration, "after": kept, "silences": len(sil)}
    log("Transcribing (faster-whisper, " + model + ")...")
    data = transcribe(tmp, model, lang, os.path.dirname(os.path.abspath(out)))
    tpl = next((t for t in load_templates() if t["id"] == template_id), load_templates()[0])
    ass = make_ass(data, tpl, w, h, main_color, high_color)
    ass_path = out + ".ass"
    open(ass_path, "w", encoding="utf-8").write(ass)
    log(f"Captions: {len(data['segments'])} lines, language {data['language']}, template {tpl['name']}")
    crf, preset = QUALITY.get(quality, QUALITY["balanced"])
    r = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", tmp,
             "-vf", f"ass={ass_path}", "-c:v", "libx264", "-crf", crf,
             "-preset", preset, "-c:a", "copy", out])
    if r.returncode != 0:
        raise RuntimeError("caption burn failed: " + r.stderr[-400:])
    os.remove(tmp)
    return {"out": out, "before": duration, "after": kept, "silences": len(sil),
            "segments": len(data["segments"]), "language": data["language"], "template": tpl["name"],
            "segments_list": [{"start": sg["start"], "end": sg["end"], "text": sg["text"]} for sg in data["segments"]]}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="SilenceCut: cut silence, add captions.")
    ap.add_argument("video", nargs="?")
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("--thresh", type=float, default=-35, help="Silence threshold dB (default -35)")
    ap.add_argument("--min-dur", type=float, default=0.55, help="Shortest silence to cut, seconds")
    ap.add_argument("--pad", type=float, default=0.12, help="Breathing room kept around speech, seconds")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--template", default="amber-karaoke")
    ap.add_argument("--lang", default="auto")
    ap.add_argument("--model", default="base")
    ap.add_argument("--main-color", default="")
    ap.add_argument("--quality", choices=["fast", "balanced", "best"], default="balanced")
    ap.add_argument("--high-color", default="")
    ap.add_argument("--list-templates", action="store_true")
    a = ap.parse_args()
    if a.list_templates:
        for t in load_templates():
            print(f"{t['id']:28s} {t['name']}  [{t['anim']}]")
        return
    out = a.out or os.path.splitext(a.video)[0] + "_cut.mp4"
    r = process(a.video, out, a.thresh, a.min_dur, a.pad, not a.no_captions,
                a.template, a.lang, a.model, a.main_color, a.high_color, quality=a.quality)
    print("DONE:", json.dumps(r))


if __name__ == "__main__":
    main()
