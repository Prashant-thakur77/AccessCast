"""M0 exit check: Gemma 4 31B answers an image prompt; Gemma 4 E4B answers a 10 s audio prompt (PLAN §22 M0)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from eval.common import Experiment, run_experiment

from accesscast.config import REPO_ROOT, load_settings
from accesscast.llm.client import LlmClient, LlmRequest

FIX = REPO_ROOT / "tests" / "fixtures" / "fixture20"


def main() -> int:
    exp = Experiment("m0_smoke", "none", config={"strict_provider": True})

    def body(e: Experiment) -> None:
        s = load_settings()
        tmp = REPO_ROOT / "projects" / "_m0"
        tmp.mkdir(parents=True, exist_ok=True)
        frame, audio = tmp / "f.jpg", tmp / "a.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                "16",
                "-i",
                str(FIX / "source.mp4"),
                "-frames:v",
                "1",
                str(frame),
            ],
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                "7",
                "-t",
                "10",
                "-i",
                str(FIX / "source.mp4"),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(audio),
            ],
            check=True,
        )
        from accesscast.llm.fake import FakeModel

        c = LlmClient(
            s,
            provider="local",
            strict_provider=True,
            log_path=tmp / "llm_calls.jsonl",
            fake_handler=FakeModel(None) if s.worker_mode == "fake" else None,
        )
        img = c.call(
            LlmRequest(
                "evidence",
                {"scene_index": 0, "frame_times_ms": [16000], "dialogue": "", "cast": [], "max_facts": 4},
                seed=0,
                images=[frame],
                label="m0:image",
            )
        )
        aud = c.call(
            LlmRequest("asr_crosscheck", {"language": "English"}, seed=0, audio=audio, label="m0:audio"),
            provider="local_audio",
        )
        e.results = [
            {
                "test": "image",
                "served_model_id": img.served_model_id,
                "latency_s": round(img.latency_s, 3),
                "facts": len(img.obj.get("visible_facts") or []),
            },
            {
                "test": "audio_10s",
                "served_model_id": aud.served_model_id,
                "latency_s": round(aud.latency_s, 3),
                "text_chars": len(str(aud.obj.get("text", ""))),
            },
        ]
        e.checks["image_answered"] = bool(img.obj.get("visible_facts"))
        e.checks["audio_answered"] = bool(str(aud.obj.get("text", "")).strip())
        e.summary = {"models": [img.served_model_id, aud.served_model_id]}

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
    _ = (json, Path)
