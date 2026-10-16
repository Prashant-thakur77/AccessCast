"""accesscast command line. Exit codes follow CLAUDE.md §6."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from accesscast.config import REPO_ROOT, load_settings
from accesscast.errors import AccessCastError, ExitCode

app = typer.Typer(
    add_completion=False, no_args_is_help=True, help="AccessCast: one video, five ways to watch."
)

ProjectOpt = Annotated[
    str, typer.Option("--project", "-p", help="project id (first 12 hex of the source SHA-256)")
]
ProviderOpt = Annotated[str, typer.Option(help="local | tokenfactory | aistudio (backup, D-023)")]


def _fail(e: BaseException) -> None:
    code = e.exit_code if isinstance(e, AccessCastError) else ExitCode.VALIDATION_FAILED
    if isinstance(e, PermissionError):
        code = ExitCode.VALIDATION_FAILED
    typer.echo(f"error: {e}", err=True)
    raise typer.Exit(int(code))


def _run(project: str, **kw: Any) -> Any:
    from accesscast.pipeline import open_run
    from accesscast.project import Project

    s = load_settings()
    return open_run(s, Project.open(s.projects_dir, project), **kw)


@app.command()
def run(
    video: Path,
    provider: ProviderOpt = "local",
    strict_provider: Annotated[bool, typer.Option("--strict-provider")] = False,
    require_rocm: Annotated[bool, typer.Option("--require-rocm")] = False,
) -> None:
    """All analysis and writing stages for one video into projects/<sha12>/ (then review)."""
    from accesscast.pipeline import run_all

    try:
        r = run_all(
            load_settings(), video, provider=provider, strict=strict_provider, require_rocm=require_rocm
        )
    except (AccessCastError, PermissionError) as e:
        _fail(e)
    typer.echo(r.project.sha12)


@app.command()
def stage(
    name: str,
    project: ProjectOpt,
    provider: ProviderOpt = "local",
    run_label: str = "run0",
    require_rocm: Annotated[bool, typer.Option("--require-rocm")] = False,
) -> None:
    """Re-run one stage alone: shots | asr | asr_crosscheck | sounds | gaps | evidence | describe | tts |
    captions | voiceover | ad_translate | review_init."""
    from accesscast import pipeline as P

    fns: dict[str, Any] = {
        "shots": P.stage_shots,
        "asr": P.stage_asr,
        "asr_crosscheck": P.stage_asr_crosscheck,
        "sounds": P.stage_sounds,
        "gaps": P.stage_gaps,
        "evidence": P.stage_evidence,
        "describe": P.stage_describe,
        "tts": P.stage_tts,
        "captions": P.stage_captions,
        "voiceover": P.stage_voiceover,
        "ad_translate": P.stage_ad_translate,
        "review_init": P.stage_review_init,
    }
    if name not in fns:
        typer.echo(f"unknown stage {name}; choose from {', '.join(fns)}", err=True)
        raise typer.Exit(int(ExitCode.USAGE))
    try:
        fns[name](_run(project, provider=provider, run_label=run_label, require_rocm=require_rocm))
    except (AccessCastError, PermissionError) as e:
        _fail(e)


@app.command()
def gate(project: ProjectOpt, versions: str = "") -> None:
    """S13: refuse while anything in the requested versions is pending or needs revision."""
    from accesscast.render_stage import AUDIENCE_VERSIONS, run_gate

    vs = [v for v in versions.split(",") if v] or [
        v for v in AUDIENCE_VERSIONS if not v.startswith("blind.h") and not v.startswith("blind.i")
    ]
    res = run_gate(_run(project), vs)
    typer.echo(
        json.dumps(
            {
                "ok": res.ok,
                "blocking": res.blocking,
                "human_reviewed": res.human_reviewed,
                "counts": res.counts,
            },
            indent=1,
        )
    )
    if not res.ok:
        raise typer.Exit(int(ExitCode.VALIDATION_FAILED))


@app.command()
def render(project: ProjectOpt, mode: str = "public", versions: str = "") -> None:
    """S14 + S15: gate, render every audience version, run render checks, package reports."""
    from accesscast.render_stage import ensure_ok, package, render_all

    try:
        r = _run(project)
        summary = render_all(r, mode=mode, versions=[v for v in versions.split(",") if v] or None)
        package(r)
        ensure_ok(summary)
    except (AccessCastError, PermissionError, ValueError) as e:
        _fail(e)
    typer.echo(f"rendered {project} ({mode})")


@app.command("translate-ad")
def translate_ad(project: ProjectOpt) -> None:
    """S11: translate APPROVED English description lines into hi/it (then review them)."""
    from accesscast.pipeline import stage_ad_translate

    try:
        stage_ad_translate(_run(project))
    except AccessCastError as e:
        _fail(e)


@app.command()
def review(port: int = 8081, host: str = "127.0.0.1") -> None:
    """Start the review app (keyboard-first; binds to localhost)."""
    import uvicorn

    from accesscast.review.server import create_app

    uvicorn.run(create_app(load_settings()), host=host, port=port, log_level="info")


@app.command("export-site")
def export_site(
    projects: str = "",
    allow_drafts: Annotated[bool, typer.Option("--allow-drafts")] = False,
    out: Path = REPO_ROOT / "site",
) -> None:
    """Copy reviewed projects into site/ (refuses drafts unless --allow-drafts, which watermarks them)."""
    from accesscast.player.build import export_site as do_export

    try:
        n = do_export(load_settings(), [p for p in projects.split(",") if p], out, allow_drafts=allow_drafts)
    except (AccessCastError, PermissionError) as e:
        _fail(e)
    typer.echo(f"exported {n} project(s) to {out}")


@app.command()
def doctor(deep: bool = False, as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Check dependencies, endpoints and (with --deep) load each model once."""
    from accesscast.doctor import run_doctor

    report = run_doctor(load_settings(), deep=deep)
    typer.echo(
        json.dumps(report, indent=1)
        if as_json
        else "\n".join(
            f"{'ok  ' if c['ok'] else 'FAIL'} {c['name']}: {c['detail']}" for c in report["checks"]
        )
    )
    if not report["ok"]:
        raise typer.Exit(int(ExitCode.MISSING_DEPENDENCY))


@app.command("schemas-export")
def schemas_export(out: Path = REPO_ROOT / "docs" / "schemas") -> None:
    """Write every data model as JSON Schema into docs/schemas/."""
    from accesscast.project import write_json
    from accesscast.schemas import EXPORTED_MODELS

    out.mkdir(parents=True, exist_ok=True)
    for name, model in EXPORTED_MODELS.items():
        write_json(out / f"{name}.schema.json", model.model_json_schema(by_alias=True))
    typer.echo(f"wrote {len(EXPORTED_MODELS)} schemas to {out}")


@app.command("claims-check")
def claims_check() -> None:
    """Verify every claim's hash and value; scan public files for unregistered numbers and placeholders."""
    from accesscast.claims import check

    res = check(REPO_ROOT, strict_placeholders=False)
    for line in res.messages:
        typer.echo(line)
    if not res.ok:
        raise typer.Exit(int(ExitCode.VALIDATION_FAILED))


@app.command("calibrate-tts")
def calibrate_tts(
    voices: str = "af_heart:en,hf_alpha:hi,if_sara:it,hm_omega:hi,im_nicola:it",
    require_rocm: Annotated[bool, typer.Option("--require-rocm")] = False,
) -> None:
    """Measure each voice's words-per-second (60 fixed sentences per language) → tts/calibration/*.json."""
    from accesscast.tts.calibrate import calibrate

    for spec in voices.split(","):
        voice, lang = spec.split(":")
        r = calibrate(voice, lang, require_rocm=require_rocm)
        typer.echo(f"{voice} ({lang}): {r['wps_voice']} words/s, intercept {r['intercept_s']} s, n={r['n']}")


@app.command("demo-fixture")
def demo_fixture(serve: bool = True, port: int = 8080) -> None:
    """Whole pipeline in fake mode on the committed 20 s fixture, draft render, then serve the player."""
    import os

    from accesscast.pipeline import FIXTURE_DIR

    os.environ["ACCESSCAST_WORKER_MODE"] = "fake"
    os.environ["ACCESSCAST_REVIEW_POLICY"] = "prototype-auto"
    os.environ.setdefault("ACCESSCAST_PROJECTS_DIR", str(REPO_ROOT / "projects" / "_fixture"))
    from accesscast.pipeline import run_all
    from accesscast.player.build import export_site as do_export
    from accesscast.render_stage import package, render_all

    s = load_settings()
    r = run_all(s, FIXTURE_DIR / "source.mp4")
    render_all(r, mode="draft")
    package(r)
    out = REPO_ROOT / "projects" / "_fixture_site"
    do_export(s, [r.project.sha12], out, allow_drafts=True)
    typer.echo(f"fixture project {r.project.sha12}; player at http://127.0.0.1:{port}/?audience=judge")
    if serve:
        from accesscast.player.serve import serve as serve_dir

        serve_dir(out, port)


@app.command("scratch-copy")
def scratch_copy(project: ProjectOpt, suffix: str = "scratch") -> None:
    """E12 manual mode: copy a project with an EMPTY description lane (lines are written by hand in the review app)."""
    import shutil

    from accesscast.project import Project, write_jsonl
    from accesscast.review.store import ReviewStore

    s = load_settings()
    src = Project.open(s.projects_dir, project).root
    dst_name = f"{project[:6]}{suffix[:6]:x<6}"  # 12 alphanumeric characters, like every project id
    dst = s.projects_dir / dst_name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("render", "review"))
    write_jsonl(dst / "items" / "ad.en.jsonl", [])
    ReviewStore(dst).init_from_items()
    typer.echo(dst_name)


def main() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(int(ExitCode.INTERRUPTED))


if __name__ == "__main__":
    main()
