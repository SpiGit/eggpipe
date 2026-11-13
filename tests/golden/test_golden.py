"""Golden-тест reference-генератора."""

from __future__ import annotations

from pathlib import Path

from reference_generator import ReferenceGenerator

from eggpipe import (
    FormatInfo,
    GenerationContext,
    GeneratorConfig,
    GeneratorInput,
    Parser,
    select_slice,
    validate_document,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_reference_generator_golden() -> None:
    document = Parser().parse_document(FIXTURES / "models" / "basic.yaml")
    assert not [item for item in validate_document(document) if item.level == "error"]
    model, diagnostics = select_slice(document.model)
    assert diagnostics == []
    config = GeneratorConfig(id="reference", output_dir=Path("out"))
    context = GenerationContext(
        formats=frozenset({FormatInfo(name=document.format, version=document.version)}),
        run_id="golden",
        config_dir=FIXTURES,
    )
    result = ReferenceGenerator().generate(
        GeneratorInput(model=model, config=config, context=context)
    )
    assert result.success
    actual = result.artifacts[0].content
    expected = (FIXTURES / "expected" / "basic.json").read_text(encoding="utf-8")
    assert actual == expected
