"""E10: fully offline (PLAN §14.6). Run ENTIRELY on the droplet: pipeline + vLLM over loopback, no SSH tunnel.

Two guard layers:
1. Python: socket connect/connect_ex/sendto/getaddrinfo/create_connection patched in the core process and, via a
   sitecustomize hook, in every worker; every blocked attempt is logged (python_blocked_attempts must be 0 —
   anything blocked means the code TRIED to reach the network).
2. Host: an nftables table counts (and drops) every outbound packet not on `lo`, except established SSH replies,
   which are excluded by rule and listed in the report. host_outbound_packets must be 0.
Outputs must equal the online run's (compare hashes with an E9 run of the same clip).
Usage (root on the droplet): python -m eval.e10_offline [--clip nasa_GSFC_20170614_Eclipse_m12534_Plane]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess

from accesscast.config import REPO_ROOT
from accesscast.guard.network import OFFLINE_ENV
from eval.common import Experiment, run_experiment
from eval.jobs import artefact_hashes, run_job

NFT = """table inet ac_offline {
  counter outbound {}
  chain out {
    type filter hook output priority 0; policy accept;
    oifname "lo" accept
    tcp sport 22 ct state established accept
    counter name outbound drop
  }
}"""


def nft(*args: str, stdin: str | None = None) -> str:
    p = subprocess.run(["nft", *args], input=stdin, capture_output=True, text=True, check=True)
    return p.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clip", default="nasa_GSFC_20170614_Eclipse_m12534_Plane")
    ap.add_argument(
        "--no-host-layer", action="store_true", help="only for local testing; E10 requires both layers"
    )
    ap.add_argument("--no-rocm", action="store_true", help="only for local testing")
    args = ap.parse_args()
    clip = REPO_ROOT / "data" / "dev" / f"{args.clip}.mp4"
    exp = Experiment(
        "e10_offline",
        "dev",
        config={
            "clip": args.clip,
            "python_layer": True,
            "host_layer": not args.no_host_layer,
            "env": OFFLINE_ENV,
            "excluded_by_rule": "established SSH replies (tcp sport 22)",
        },
    )

    def body(e: Experiment) -> None:
        log = REPO_ROOT / "projects" / "_e10" / "guard.jsonl"
        shutil.rmtree(log.parent, ignore_errors=True)
        log.parent.mkdir(parents=True)
        env = {
            **OFFLINE_ENV,
            "ACCESSCAST_OFFLINE": "1",
            "ACCESSCAST_GUARD_LOG": str(log),
            "ACCESSCAST_SRC": str(REPO_ROOT / "src"),
            "PYTHONPATH": os.pathsep.join(
                [str(REPO_ROOT / "src" / "accesscast" / "guard" / "site"), os.environ.get("PYTHONPATH", "")]
            ),
        }
        if not args.no_host_layer:
            subprocess.run(["nft", "delete", "table", "inet", "ac_offline"], capture_output=True)
            nft("-f", "-", stdin=NFT)
        try:
            r = run_job(clip, log.parent / "proj", env=env, require_rocm=not args.no_rocm)
        finally:
            host = None
            if not args.no_host_layer:
                out = nft("-j", "list", "counter", "inet", "ac_offline", "outbound")
                for obj in json.loads(out)["nftables"]:
                    if "counter" in obj:
                        host = int(obj["counter"]["packets"])
                subprocess.run(["nft", "delete", "table", "inet", "ac_offline"], capture_output=True)
        blocked = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
        e.results = blocked[:200]
        e.summary["python_blocked_attempts"] = len(blocked)
        e.summary["host_outbound_packets"] = host
        e.summary["job_ok"] = r.ok
        e.summary["job_error"] = r.error
        if r.sha12:
            e.summary["output_hashes"] = artefact_hashes(log.parent / "proj" / r.sha12)
        e.checks["job_ok"] = r.ok
        e.checks["python_layer_zero"] = len(blocked) == 0
        e.checks["host_layer_zero"] = host == 0
        # Prove the hook is live in workers: a worker-side lookup must be blocked and logged by the guard.
        probe = subprocess.run(
            [
                "python3",
                "-s",
                "-c",
                "import socket\ntry:\n socket.getaddrinfo('example.com',80)\nexcept Exception: pass",
            ],
            env={**os.environ, **env},
            capture_output=True,
            text=True,
        )
        logged = len(log.read_text().splitlines()) if log.exists() else 0
        e.summary["guard_self_test_blocked"] = logged - len(blocked)
        e.checks["guard_self_test"] = logged - len(blocked) >= 1
        _ = probe

    return run_experiment(exp, body)


if __name__ == "__main__":
    raise SystemExit(main())
