# Eggpipe

<p align="center">
  <img src="https://raw.githubusercontent.com/SpiGit/eggpipe/main/docs/assets/brand/lockup/eggpipe-wordmark-light.png" alt="Eggpipe" width="420">
</p>

Eggpipe generates SQL, Python, TypeScript, OpenAPI and other artifacts from a single
YAML model description.

> **Beta (0.x).** Until 1.0, the public API, CLI, config format and generated artifacts
> may change without backward compatibility. Pin the version for production and read
> the changelog before upgrading.

## Install

```bash
pip install eggpipe
```

Python 3.11+ is required.

Optional extras:

```bash
pip install "eggpipe[watch]"   # watch mode
pip install "eggpipe[jinja]"   # Jinja2 helper for plugins
```

## CLI

```bash
eggpipe init
eggpipe generate model.yaml
eggpipe generate --plan
eggpipe generate --check
eggpipe watch model.yaml
```

## Library

```python
from eggpipe import AppConfig, Engine, ProjectConfigLoader

rules = ProjectConfigLoader().load(".eggpipe.yaml")
engine = Engine(AppConfig(), rules)

report = engine.build()       # parse, validate and generate without writing
report = engine.generate()    # build + write artifacts
report = engine.check()       # check drift without writing

if not report.success:
    for diagnostic in report.diagnostics:
        print(diagnostic.code, diagnostic.message)
```

## Plugins

Generators and document formats are plugins registered through entry points:

```toml
[project.entry-points."eggpipe.generators"]
my-generator = "my_package:my_generator"

[project.entry-points."eggpipe.formats"]
sql-model = "my_package:SqlModelFormat"
```

## Documentation

- [Documentation](https://github.com/SpiGit/eggpipe/tree/main/docs)
- [Quick start](https://github.com/SpiGit/eggpipe/blob/main/docs/user/quickstart.md)
- [CLI reference](https://github.com/SpiGit/eggpipe/blob/main/docs/user/cli.md)
- [Plugin guide](https://github.com/SpiGit/eggpipe/blob/main/docs/user/plugins.md)
- [Changelog](https://github.com/SpiGit/eggpipe/blob/main/CHANGELOG.md)
- [Issues](https://github.com/SpiGit/eggpipe/issues)

## License

MIT
