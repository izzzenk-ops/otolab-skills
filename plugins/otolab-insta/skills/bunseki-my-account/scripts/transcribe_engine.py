#!/usr/bin/env python3
"""文字起こしエンジンをOSで出し分ける共通モジュール。

- Apple Silicon Mac → mlx_whisper（既存スキルと同じ・高速。~/telop-tool/venv に導入）
- それ以外（Windows など） → faster-whisper（CPUで動く・クロスプラットフォーム）

pipeline.py / transcribe.py はこの関数だけを呼ぶので、
OSごとの違いをここに閉じ込められる。

公開関数:
  transcribe_file(path, language="ja") -> (text: str, segments: list[dict])
    segments = [{"start": float, "end": float, "text": str}, ...]
"""
import platform
import sys


def is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


if is_apple_silicon():
    # ---- Mac (Apple Silicon): mlx_whisper -----------------------------------
    import mlx_whisper

    MODEL = "mlx-community/whisper-large-v3-turbo"
    ENGINE = "mlx_whisper"

    def transcribe_file(path, language="ja"):
        r = mlx_whisper.transcribe(
            str(path), path_or_hf_repo=MODEL, language=language, fp16=True)
        text = r["text"].strip()
        segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2),
                 "text": s["text"].strip()}
                for s in r.get("segments", [])]
        return text, segs

else:
    # ---- Windows / その他: faster-whisper -----------------------------------
    from faster_whisper import WhisperModel

    # CPUでも動く構成。turboが使えない環境向けに large-v3 を既定にする。
    MODEL = "large-v3"
    ENGINE = "faster_whisper"
    _model = None

    def _get_model():
        global _model
        if _model is None:
            # int8でCPUメモリと速度のバランスを取る
            _model = WhisperModel(MODEL, device="cpu", compute_type="int8")
        return _model

    def transcribe_file(path, language="ja"):
        segments, _info = _get_model().transcribe(str(path), language=language)
        parts, segs = [], []
        for s in segments:  # ジェネレータ。1回だけ回す
            parts.append(s.text)
            segs.append({"start": round(s.start, 2), "end": round(s.end, 2),
                         "text": s.text.strip()})
        return "".join(parts).strip(), segs
