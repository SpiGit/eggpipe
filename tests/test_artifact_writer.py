"""Writer tests: paths, ownership, global manifest, lock."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

import pytest

from eggpipe import Artifact, Diagnostic
from eggpipe.core.model import FormatInfo
from eggpipe.engine.artifact_writer import ArtifactWriter, ExecutionPlan
from eggpipe.utils.exceptions import LockError, ManifestError


def writer(tmp_path: Path) -> ArtifactWriter:
    return ArtifactWriter(eggpipe_version="0.3.2", config_dir=tmp_path)


def plan_for(
    tmp_path: Path,
    output: Path,
    *artifacts: Artifact,
    generator_id: str = "gen",
    on_conflict: str = "overwrite",
    force: bool = False,
    formats: frozenset[FormatInfo] = frozenset(),
):
    return writer(tmp_path).plan(
        generator_id=generator_id,
        output_dir=output,
        artifacts=list(artifacts),
        on_conflict=on_conflict,  # type: ignore[arg-type]
        force=force,
        formats=formats,
    )


def write(
    tmp_path: Path,
    output: Path,
    plan: ExecutionPlan,
    *,
    generator_id: str = "gen",
    cleanup: str = "off",
) -> list[Diagnostic]:
    return writer(tmp_path).write(
        generator_id=generator_id,
        output_dir=output,
        plan=plan,
        plugin_version="1.0",
        cleanup=cleanup,  # type: ignore[arg-type]
    )


def location(tmp_path: Path, generator_id: str = "gen", output: str = "out"):
    manifest = writer(tmp_path).load_manifest()
    return next(
        item
        for item in manifest.locations
        if item.generator == generator_id and item.output_dir == output
    )


def test_create_and_global_manifest(tmp_path: Path) -> None:
    output = tmp_path / "out"
    plan = plan_for(
        tmp_path,
        output,
        Artifact(path="a.txt", content="hello\n"),
        formats=frozenset({FormatInfo("entity-model", "1.0")}),
    )
    assert [item.action for item in plan.artifacts] == ["create"]
    write(tmp_path, output, plan)
    assert (output / "a.txt").read_text(encoding="utf-8") == "hello\n"
    manifest = writer(tmp_path).load_manifest()
    assert manifest.manifest_version == 2
    assert (tmp_path / ".eggpipe" / "manifest.json").is_file()
    loc = location(tmp_path)
    assert loc.formats[0].name == "entity-model"
    assert loc.artifacts[0].path == "a.txt"
    assert loc.artifacts[0].skipped is False


def test_path_traversal_and_invalid_content(tmp_path: Path) -> None:
    output = tmp_path / "out"
    for artifact in (
        Artifact(path="../escape.txt", content="x"),
        Artifact(path="/absolute.txt", content="x"),
        Artifact(path="CON", content="x"),
        Artifact(path="C:drive.txt", content="x"),
        Artifact(path="a.txt", content="\ufeffbom"),
        Artifact(path="a.txt", content="crlf\r\n"),
    ):
        plan = plan_for(tmp_path, output, artifact)
        assert plan.diagnostics[0].code == "EG040"


def test_case_collision(tmp_path: Path) -> None:
    output = tmp_path / "out"
    plan = plan_for(
        tmp_path,
        output,
        Artifact(path="A.txt", content="a"),
        Artifact(path="a.txt", content="b"),
    )
    assert plan.diagnostics[0].code == "EG042"


def test_non_owned_requires_force(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    target = output / "a.txt"
    target.write_text("old", encoding="utf-8")
    blocked = plan_for(tmp_path, output, Artifact(path="a.txt", content="new"))
    assert blocked.diagnostics[0].code == "EG041"
    allowed = plan_for(tmp_path, output, Artifact(path="a.txt", content="new"), force=True)
    assert allowed.artifacts[0].action == "update"
    write(tmp_path, output, allowed)
    assert target.read_text(encoding="utf-8") == "new"


def test_owned_update_and_skip(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(tmp_path, output, plan_for(tmp_path, output, Artifact(path="a.txt", content="one")))
    plan = plan_for(tmp_path, output, Artifact(path="a.txt", content="two"))
    assert plan.artifacts[0].action == "update"
    error_plan = plan_for(
        tmp_path,
        output,
        Artifact(path="a.txt", content="two"),
        on_conflict="error",
    )
    assert error_plan.diagnostics[0].code == "EG041"
    skipped = plan_for(
        tmp_path,
        output,
        Artifact(path="a.txt", content="three"),
        on_conflict="skip",
    )
    assert skipped.artifacts[0].action == "skip"
    write(tmp_path, output, skipped)
    assert (output / "a.txt").read_text(encoding="utf-8") == "one"
    assert location(tmp_path).artifacts[0].skipped is True


def test_skip_non_owned_does_not_claim(tmp_path: Path) -> None:
    output = tmp_path / "out"
    output.mkdir()
    (output / "a.txt").write_text("user", encoding="utf-8")
    plan = plan_for(
        tmp_path,
        output,
        Artifact(path="a.txt", content="new"),
        on_conflict="skip",
    )
    assert plan.artifacts == []
    assert plan.diagnostics[0].code == "EG043"
    write(tmp_path, output, plan)
    assert writer(tmp_path).load_manifest().locations == []


def test_force_does_not_take_file_from_other_location(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(
        tmp_path,
        output,
        plan_for(
            tmp_path,
            output,
            Artifact(path="same.txt", content="one"),
            generator_id="first",
        ),
        generator_id="first",
    )
    blocked = plan_for(
        tmp_path,
        output,
        Artifact(path="same.txt", content="two"),
        generator_id="second",
        force=True,
    )
    assert blocked.diagnostics[0].code == "EG041"
    assert "first" in blocked.diagnostics[0].message


def test_check_detects_drift(tmp_path: Path) -> None:
    output = tmp_path / "out"
    plan = plan_for(tmp_path, output, Artifact(path="a.txt", content="one"))
    write(tmp_path, output, plan)
    assert writer(tmp_path).check(plan=plan) == []
    (output / "a.txt").write_text("changed", encoding="utf-8")
    assert writer(tmp_path).check(plan=plan)[0].code == "EG300"


def test_lock(tmp_path: Path) -> None:
    instance = writer(tmp_path)
    with instance.write_lock(), pytest.raises(LockError), instance.write_lock():
        pass


def test_stale_lock_is_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from eggpipe.engine import artifact_writer

    lock = tmp_path / ".eggpipe" / "lock"
    lock.parent.mkdir()
    lock.write_text("999999\n", encoding="utf-8")

    def never_alive(pid: int) -> bool:
        return False

    monkeypatch.setattr(artifact_writer, "_pid_alive", never_alive)
    with writer(tmp_path).write_lock():
        pass
    assert not lock.exists()


def test_staging_sweep(tmp_path: Path) -> None:
    output = tmp_path / "out"
    stale = output / ".eggpipe-staging-old" / "nested"
    stale.mkdir(parents=True)
    write(tmp_path, output, plan_for(tmp_path, output, Artifact(path="a.txt", content="a")))
    assert not (output / ".eggpipe-staging-old").exists()


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    output = tmp_path / "out"
    outside = tmp_path / "outside"
    output.mkdir()
    outside.mkdir()
    try:
        (output / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink is not available on this platform")
    plan = plan_for(tmp_path, output, Artifact(path="link/escape.txt", content="x"))
    assert plan.diagnostics[0].code == "EG040"


def test_cleanup_off_keeps_stale_entries(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(tmp_path, output, plan_for(tmp_path, output, Artifact(path="old.txt", content="old")))
    write(tmp_path, output, plan_for(tmp_path, output, Artifact(path="new.txt", content="new")))
    assert (output / "old.txt").is_file()
    assert {item.path for item in location(tmp_path).artifacts} == {"old.txt", "new.txt"}


def test_cleanup_enabled_removes_unchanged_stale(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(tmp_path, output, plan_for(tmp_path, output, Artifact(path="old.txt", content="old")))
    write(
        tmp_path,
        output,
        plan_for(tmp_path, output, Artifact(path="new.txt", content="new")),
        cleanup="enabled",
    )
    assert not (output / "old.txt").exists()
    assert {item.path for item in location(tmp_path).artifacts} == {"new.txt"}


def test_cleanup_keeps_modified_owned_file(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(tmp_path, output, plan_for(tmp_path, output, Artifact(path="old.txt", content="old")))
    (output / "old.txt").write_text("user edit", encoding="utf-8")
    diagnostics = write(
        tmp_path,
        output,
        plan_for(tmp_path, output, Artifact(path="new.txt", content="new")),
        cleanup="enabled",
    )
    assert (output / "old.txt").read_text(encoding="utf-8") == "user edit"
    assert diagnostics[0].code == "EG050"
    assert {item.path for item in location(tmp_path).artifacts} == {"old.txt", "new.txt"}


def test_clean_all_locations_and_remove_manifest(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    write(
        tmp_path,
        first,
        plan_for(tmp_path, first, Artifact(path="a.txt", content="a"), generator_id="first"),
        generator_id="first",
    )
    write(
        tmp_path,
        second,
        plan_for(tmp_path, second, Artifact(path="b.txt", content="b"), generator_id="second"),
        generator_id="second",
    )
    result = writer(tmp_path).clean()
    assert result.removed_artifacts == 2
    assert result.removed_locations == 2
    assert not (first / "a.txt").exists()
    assert not (second / "b.txt").exists()
    assert not (tmp_path / ".eggpipe" / "manifest.json").exists()


def test_clean_dry_run_keeps_files(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(tmp_path, output, plan_for(tmp_path, output, Artifact(path="a.txt", content="a")))
    result = writer(tmp_path).clean(dry_run=True)
    assert result.removed_artifacts == 1
    assert (output / "a.txt").is_file()
    assert (tmp_path / ".eggpipe" / "manifest.json").is_file()


def test_manifest_v1_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe" / "manifest.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"manifest_version": 1, "locations": []}), encoding="utf-8")
    with pytest.raises(ManifestError):
        writer(tmp_path).load_manifest()


def test_corrupted_manifest_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / ".eggpipe" / "manifest.json"
    path.parent.mkdir()
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ManifestError):
        writer(tmp_path).load_manifest()


def test_empty_plan_runs_cleanup_for_previous_location(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(tmp_path, output, plan_for(tmp_path, output, Artifact(path="old.txt", content="old")))
    write(
        tmp_path,
        output,
        plan_for(tmp_path, output),
        cleanup="enabled",
    )
    assert not (output / "old.txt").exists()
    assert writer(tmp_path).load_manifest().locations == []


def test_pending_deletions_for_cleanup(tmp_path: Path) -> None:
    output = tmp_path / "out"
    write(tmp_path, output, plan_for(tmp_path, output, Artifact(path="old.txt", content="old")))
    plan = plan_for(tmp_path, output, Artifact(path="new.txt", content="new"))
    instance = writer(tmp_path)
    assert (
        instance.pending_deletions(
            generator_id="gen",
            output_dir=output,
            plan=plan,
            cleanup="off",
        )
        == []
    )
    assert instance.pending_deletions(
        generator_id="gen",
        output_dir=output,
        plan=plan,
        cleanup="enabled",
    ) == [PurePosixPath("old.txt")]
