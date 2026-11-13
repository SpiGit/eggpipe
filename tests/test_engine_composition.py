"""Engine: imports, extends, discovery и resources."""

from __future__ import annotations

from pathlib import Path

from eggpipe import (
    AppConfig,
    Artifact,
    Engine,
    GenerationResult,
    GeneratorConfig,
    GeneratorInput,
    GeneratorPlugin,
    GeneratorRules,
    SourceConfig,
)
from eggpipe.config.generator_rules import DiagnosticsConfig, InputSlice

BASE = """\
format: entity-model
version: "1.0"
model:
  entities:
    - name: Audit
      fields:
        - name: id
          type: integer
        - name: created_at
          type: datetime
"""

POST = """\
format: entity-model
version: "1.0"
model:
  imports:
    - path: ./base.yaml
      as: audit
  entities:
    - name: Post
      extends: Audit
      fields:
        - name: title
          type: string
"""


class CaptureGenerator(GeneratorPlugin):
    id = "capture"
    name = "Capture"

    def generate(self, input: GeneratorInput) -> GenerationResult:
        imports = ",".join(sorted(input.context.imports))
        fields = ",".join(field.name for field in input.model.entity("Post").fields)
        return GenerationResult(
            artifacts=[Artifact(path="result.txt", content=f"{fields}|{imports}\n")]
        )


def make_engine(tmp_path: Path, *, allow_outside: bool = False) -> Engine:
    rules = GeneratorRules(
        version="1.0",
        sources=(SourceConfig(path=Path("models")),),
        generators=(GeneratorConfig(id="capture", output_dir=Path("out")),),
    )
    return Engine(
        AppConfig(allow_outside_imports=allow_outside),
        rules,
        config_dir=tmp_path,
        generators={"capture": CaptureGenerator()},
    )


def test_directory_sources_composition(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "base.yaml").write_text(BASE, encoding="utf-8")
    (models / "post.yaml").write_text(POST, encoding="utf-8")
    (models / "icon.svg").write_text("<svg/>", encoding="utf-8")
    # Resource import is declared relative to post.yaml.
    (models / "post.yaml").write_text(
        POST.replace(
            "    - path: ./base.yaml\n      as: audit\n",
            "    - path: ./base.yaml\n      as: audit\n    - path: ./icon.svg\n      as: icon\n",
        ),
        encoding="utf-8",
    )
    report = make_engine(tmp_path).generate()
    assert report.success is True
    content = (tmp_path / "out" / "result.txt").read_text(encoding="utf-8")
    assert content == "id,created_at,title|icon\n"


def test_outside_imports_require_flag(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "shared.yaml"
    outside.write_text(BASE, encoding="utf-8")
    models = root / "models"
    models.mkdir()
    (models / "post.yaml").write_text(
        POST.replace("./base.yaml", "../../shared.yaml"), encoding="utf-8"
    )
    blocked = make_engine(root).generate()
    assert blocked.success is False
    assert any(item.code == "MG022" for item in blocked.diagnostics)
    allowed = make_engine(root, allow_outside=True).generate()
    assert allowed.success is True


def test_source_input_through_engine(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    (models / "base.yaml").write_text(BASE, encoding="utf-8")
    (models / "post.yaml").write_text(POST, encoding="utf-8")
    rules = GeneratorRules(
        version="1.0",
        sources=(
            SourceConfig(
                path=Path("models"),
                input=InputSlice(entities=("Post",)),
            ),
        ),
        generators=(GeneratorConfig(id="capture", output_dir=Path("out")),),
    )
    engine = Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={"capture": CaptureGenerator()},
    )
    report = engine.generate()
    assert report.success is True
    content = (tmp_path / "out" / "result.txt").read_text(encoding="utf-8")
    assert content == "id,created_at,title|\n"


def test_stale_dates_opt_in(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(
        BASE.replace(
            "    - name: Audit\n",
            "    - name: Audit\n      updated_at: 2000-01-01\n",
        ),
        encoding="utf-8",
    )
    rules = GeneratorRules(
        version="1.0",
        diagnostics=DiagnosticsConfig(stale_dates=True),
        sources=(SourceConfig(path=Path("model.yaml")),),
        generators=(GeneratorConfig(id="capture", output_dir=Path("out")),),
    )
    engine = Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={"capture": CaptureGenerator()},
    )
    report = engine.build()
    assert "MG014" in {item.code for item in report.diagnostics}


def test_stale_dates_disabled_by_default(tmp_path: Path) -> None:
    (tmp_path / "model.yaml").write_text(
        BASE.replace(
            "    - name: Audit\n",
            "    - name: Audit\n      updated_at: 2000-01-01\n",
        ),
        encoding="utf-8",
    )
    rules = GeneratorRules(
        version="1.0",
        sources=(SourceConfig(path=Path("model.yaml")),),
        generators=(GeneratorConfig(id="capture", output_dir=Path("out")),),
    )
    engine = Engine(
        AppConfig(),
        rules,
        config_dir=tmp_path,
        generators={"capture": CaptureGenerator()},
    )
    assert "MG014" not in {item.code for item in engine.build().diagnostics}
