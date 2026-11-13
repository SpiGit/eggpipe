"""Golden и contract-проверки TPC-H example."""

from __future__ import annotations

from pathlib import Path

from tpch_generator import (
    TpchDdlGenerator,
    TpchGenerator,
    TpchPydanticGenerator,
)

from eggpipe import (
    AppConfig,
    Engine,
    GeneratorRulesLoader,
    Parser,
)

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "examples" / "tpc-h"
EXPECTED = EXAMPLE / "expected"


def test_tpch_single_generator_golden(tmp_path: Path) -> None:
    engine = Engine(
        AppConfig(output_root=tmp_path),
        GeneratorRulesLoader().load(EXAMPLE / ".eggpipe.yaml"),
        config_dir=EXAMPLE,
        generators={"tpch": TpchGenerator()},
    )
    report = engine.generate()
    assert report.success is True
    assert (tmp_path / "generated" / "postgres" / "schema.sql").read_text(encoding="utf-8") == (
        EXPECTED / "schema.sql"
    ).read_text(encoding="utf-8")
    assert (tmp_path / "generated" / "python" / "tpch_models.py").read_text(encoding="utf-8") == (
        EXPECTED / "tpch_models.py"
    ).read_text(encoding="utf-8")


def test_tpch_split_generators_golden(tmp_path: Path) -> None:
    engine = Engine(
        AppConfig(output_root=tmp_path),
        GeneratorRulesLoader().load(EXAMPLE / ".eggpipe.split.yaml"),
        config_dir=EXAMPLE,
        generators={
            "tpch-ddl": TpchDdlGenerator(),
            "tpch-pydantic": TpchPydanticGenerator(),
        },
    )
    report = engine.generate()
    assert report.success is True
    assert (tmp_path / "generated" / "postgres" / "schema.sql").is_file()
    assert (tmp_path / "generated" / "python" / "tpch_models.py").is_file()


def test_tpch_custom_templates(tmp_path: Path) -> None:
    from tpch_generator.ddl import render_ddl
    from tpch_generator.pydantic_models import render_pydantic

    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "schema.sql.j2").write_text(
        "-- custom\n{% for table in tables %}TABLE {{ table.name }}\n{% endfor %}",
        encoding="utf-8",
    )
    (templates / "pydantic.py.j2").write_text(
        (
            "{% for entity in entities %}class {{ entity.name }}: "
            "{% for field in entity.fields %}{{ field.name }} {% endfor %}\n"
            "{% endfor %}"
        ),
        encoding="utf-8",
    )
    document = Parser().parse_document(EXAMPLE / "model" / "region" / "base.yaml")

    assert render_ddl(document.model, templates_dir=templates) == "-- custom\nTABLE region\n"

    models = render_pydantic(document.model, templates_dir=templates)
    assert models == "class Region: r_regionkey r_name r_comment "
