# Development

## Project workflow

For implementation changes, the safest loop is:

1. make a focused code change
2. run syntax validation
3. run the unit and integration-style tests
4. run a real build smoke test when the change affects actual build orchestration

## Test commands

Full suite:

```bash
python3 -m unittest discover -s tests
```

Focused wrapper:

```bash
python3 run_tests.py
```

Syntax validation:

```bash
python3 -m py_compile cli.py core/*.py tests/*.py
```

## Documentation build

Install doc dependencies:

```bash
python3 -m pip install -r docs/requirements.txt
```

Build HTML docs:

```bash
make -C docs html
```

## Adding a new profile

Choose the appropriate config subdirectory and add a JSON file:

- desktop profile: `configs/desktops/`
- kernel profile: `configs/kernels/`
- package bundle: `configs/packages/`
- service bundle: `configs/services/`
- live-user preset: `configs/live-users/`

Then verify it appears in:

```bash
python3 cli.py --list-options
```

## Adding a new architecture engine

Add or register a new engine under `core.iso_engine` and ensure the architecture profile exists under `configs/architectures/`.

## Documentation strategy

The repository now contains two documentation layers:

- `README.md` for fast onboarding and common commands
- `docs/` for structured Sphinx documentation and API reference

## Config profile maintenance

When adding or changing files under `configs/`, update the matching page under `docs/profiles/` so the profile catalog stays aligned with the repository.