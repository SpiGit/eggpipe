"""Тесты writer: пути, ownership, manifest, lock."""

from __future__ import annotations

from pathlib import Path

import pytest

from metadata_generator import Artifact, Diagnostic
from metadata_generator.engine.artifact_writer import ArtifactWriter, ExecutionPlan
from metadata_generator.utils.exceptions import LockError


def writer() -> ArtifactWriter:
    return ArtifactWriter(mg_version="0.1.0")


def plan_for(
    output: Path,
    *artifacts: Artifact,
    on_conflict: str = "overwrite",
    force: bool = False,
):
    return writer().plan(
        generator_id="gen",
        output_dir=output,
        artifacts=list(artifacts),
        on_conflict=on_conflict,  # type: ignore[arg-type]
        force=force,
    )


def write(output: Path, plan: ExecutionPlan, cleanup: str = "off") -> list[Diagnostic]:
    return writer().write(
        generator_id="gen",
        output_dir=output,
        plan=plan,
        plugin_version="1.0",
        format_name="entity-model",
        format_version="1.0",
        cleanup=cleanup,  # type: ignore[arg-type]
    )


def test_create_and_manifest(tmp_path: Path) -> None:
    output = tmp_path / "out"
    plan = plan_for(output, Artifact(path="a.txt", content="hello\n"))
    assert [item.action for item in plan.artifacts] == ["create"]
    write(output, plan)
    assert (output / "a.txt").read_text(encoding="utf-8") == "hello\n"
    manifest = writer().load_manifest(output, "gen")
    assert manifest.artifacts[0].path == "a.txt"
    assert manifest.artifacts[0].skipped is False


def test_path_traversal_and_invalid_content(tmp_path: Path) -> None:
    output = tmp_path / "out"
    for artifact in (
        Artifact(path="../escape.txt", content="x"),
        Artifact(path="/absolute.txt", content="x"),
        Artifact(path="CON", content="x"),
        Artifact(path="a.txt", content="\ufeffbom"),
        Artifact(path="a.txt", content="crlf\r\n"),
    ):
        plan = plan_for(output, artifact)
        assert plan.diagnostics[0].code == "MG040"


def test_case_collision(tmp_path: Path) -> None:
    output = tmp_path / "out"
    plan = plan_for(
        output,
        Artifact(path="A.txt", content="a"),
        Artifact(path="a.txt", content="b"),
    )
    assert plan.diagnostics[0].code == "MG042"


def test_non_owned_requires_force(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    target = output / "a.txt"
    target.write_text("old", encoding="utf-8")
    blocked = plan_for(output, Artifact(path="a.txt", content="new"))
    assert blocked.diagnostics[0].code == "MG041"
    allowed = plan_for(output, Artifact(path="a.txt", content="new"), force=True)
    assert allowed.artifacts[0].action == "update"
    write(output, allowed)
    assert target.read_text(encoding="utf-8") == "new"


def test_owned_update_and_skip(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(output, plan_for(output, Artifact(path="a.txt", content="one")))
    plan = plan_for(output, Artifact(path="a.txt", content="two"))
    assert plan.artifacts[0].action == "update"
    skipped = plan_for(output, Artifact(path="a.txt", content="three"), on_conflict="skip")
    assert skipped.artifacts[0].action == "skip"
    write(output, skipped)
    assert (output / "a.txt").read_text(encoding="utf-8") == "one"
    manifest = writer().load_manifest(output, "gen")
    assert manifest.artifacts[0].skipped is True


def test_skip_non_owned_does_not_claim(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "a.txt").write_text("user", encoding="utf-8")
    plan = plan_for(output, Artifact(path="a.txt", content="new"), on_conflict="skip")
    assert plan.artifacts == []
    assert plan.diagnostics[0].code == "MG043"
    write(output, plan)
    manifest = writer().load_manifest(output, "gen")
    assert manifest.artifacts == []


def test_check_detects_drift(tmp_path: Path) -> None:
    output = tmp_path / "out"
    plan = plan_for(output, Artifact(path="a.txt", content="one"))
    write(output, plan)
    assert writer().check(output_dir=output, plan=plan) == []
    (output / "a.txt").write_text("changed", encoding="utf-8")
    assert writer().check(output_dir=output, plan=plan)[0].code == "MG300"


def test_lock(tmp_path: Path) -> None:
    output = tmp_path / "out"
    with writer().write_lock(output), pytest.raises(LockError), writer().write_lock(output):
        pass


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "out"
    outside = tmp_path / "outside"
    output.mkdir()
    outside.mkdir()
    try:
        (output / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink недоступен на платформе")
    plan = plan_for(output, Artifact(path="link/escape.txt", content="x"))
    assert plan.diagnostics[0].code == "MG040"


def test_cleanup_off_keeps_stale_entries(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(output, plan_for(output, Artifact(path="old.txt", content="old")))
    write(output, plan_for(output, Artifact(path="new.txt", content="new")))
    assert (output / "old.txt").is_file()
    manifest = writer().load_manifest(output, "gen")
    assert {item.path for item in manifest.artifacts} == {"old.txt", "new.txt"}


def test_cleanup_enabled_removes_unchanged_stale(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(output, plan_for(output, Artifact(path="old.txt", content="old")))
    write(
        output,
        plan_for(output, Artifact(path="new.txt", content="new")),
        cleanup="enabled",
    )
    assert not (output / "old.txt").exists()
    manifest = writer().load_manifest(output, "gen")
    assert {item.path for item in manifest.artifacts} == {"new.txt"}


def test_cleanup_keeps_modified_owned_file(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(output, plan_for(output, Artifact(path="old.txt", content="old")))
    (output / "old.txt").write_text("user edit", encoding="utf-8")
    diagnostics = write(
        output,
        plan_for(output, Artifact(path="new.txt", content="new")),
        cleanup="enabled",
    )
    assert (output / "old.txt").read_text(encoding="utf-8") == "user edit"
    assert diagnostics[0].code == "MG050"
    manifest = writer().load_manifest(output, "gen")
    assert {item.path for item in manifest.artifacts} == {"old.txt", "new.txt"}


def test_clean_manifest(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(output, plan_for(output, Artifact(path="a.txt", content="a")))
    write(output, plan_for(output, Artifact(path="b.txt", content="b")))
    diagnostics = writer().clean_manifest(output_dir=output, generator_id="gen", dry_run=False)
    assert diagnostics == []
    assert not (output / "a.txt").exists()
    assert not (output / "b.txt").exists()
    manifest = writer().load_manifest(output, "gen")
    assert manifest.artifacts == []
