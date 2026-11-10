#!/usr/bin/env python3
"""Transcribe helper: run with a python that has faster_whisper installed.
Decodes the WAV with the stdlib wave module and feeds faster-whisper a
numpy array (avoids PyAV version breakage entirely).
Usage: transcribe.py <wav16k-mono> <model> <language|auto> <out.json>"""
import json, sys, wave
import numpy as np
from faster_whisper import WhisperModel

wav_path, model, lang, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
w = wave.open(wav_path, "rb")
frames = w.readframes(w.getnframes())
audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
m = WhisperModel(model, device="cpu", compute_type="int8")
segments, info = m.transcribe(audio, language=None if lang == "auto" else lang,
                              word_timestamps=True, vad_filter=True)
data = {"language": info.language, "segments": []}
for s in segments:
    data["segments"].append({
        "start": s.start, "end": s.end, "text": s.text.strip(),
        "words": [{"start": ww.start, "end": ww.end, "word": ww.word.strip()}
                  for ww in (s.words or []) if ww.word.strip()]})
json.dump(data, open(out, "w"))
print("transcribed", len(data["segments"]), "segments, language:", data["language"])
