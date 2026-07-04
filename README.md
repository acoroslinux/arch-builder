# Arch-Builder

Arch-Builder is a modular Arch Linux ISO builder written in Python. It assembles build profiles from JSON configuration files, prepares a target root filesystem, applies customizations, configures bootloaders, and produces a final ISO image.

The project supports two execution modes:

- `mock`: safe simulation mode for development and tests.
- `real`: actual ISO construction with chroot operations and optional isolated Arch bootstrap tooling.

## Highlights

- Profile-driven builds for architecture, desktop, kernel, bootloader, packages, services, and live-user presets.
- Real isolated build-host bootstrap for running on non-Arch Linux distributions.
- Workspace-local build tree and reusable pacman cache.
- Dynamic output naming based on desktop and architecture.
- Test suite covering configuration assembly and real-like orchestration behavior.

## Repository Layout

```text
arch-builder/
├── cli.py
├── configs/
│   ├── architectures/
│   ├── bootloaders/
│   ├── custom-packages/
│   ├── custom_files/
│   ├── desktops/
│   ├── kernels/
│   ├── live-users/
│   ├── packages/
│   ├── services/
│   └── templates/
├── core/
├── docs/
├── tests/
└── utils/
```

## Requirements

## Runtime

- Python 3.10+
- Linux host

## Real build mode tools

When using host tooling directly, these programs are expected to exist on the system:

- `pacman`
- `grub-mkrescue`
- `genisoimage`
- `mksquashfs`
- `xorriso`

If they do not exist, `--mode real` can bootstrap an isolated Arch toolchain with `--force-isolated-toolchain`, or it can do so automatically when host tools are unavailable.

## Quick Start

## Show available profiles

```bash
python3 cli.py --list-options
```

## Mock build

```bash
python3 cli.py x86_64 --desktop xfce
```

Default output naming is dynamic when `-o/--output` is not provided:

```text
arch-builder-<desktop>-<architecture>.iso
```

Examples:

- `arch-builder-xfce-x86_64.iso`
- `arch-builder-base-x86_64.iso`

## Real build with isolated toolchain

```bash
sudo python3 cli.py \
  x86_64 \
  --mode real \
  --desktop xfce \
  --force-isolated-toolchain \
  --toolchain-debug \
  --toolchain-debug-log arch-builder/toolchain-debug.log \
  --toolchain-pacman-retries 4
```

## Build Artifacts

By default, the project uses visible workspace-local paths:

- `arch-builder/workdir/`
- `arch-builder/fallback/`
- `arch-builder/cache/pacman/pkg/`

These defaults keep build state inside the repository workspace while allowing pacman cache reuse across builds.

## CLI Reference

Run:

```bash
python3 cli.py --help
```

Key flags:

- `--mode {mock,real}`: choose simulation or real build execution.
- `--clean`: remove previous build artifacts before building.
- `--no-clean`: reuse an existing build tree.
- `--force-isolated-toolchain`: always bootstrap and use the isolated Arch build host.
- `--toolchain-debug`: enable toolchain diagnostics logging.
- `--toolchain-debug-log PATH`: explicit diagnostics log path.
- `--toolchain-pacman-retries N`: retry count for `pacman` and `pacman-key` during isolated bootstrap.
- `--desktop NAME`: desktop profile override from `configs/desktops/`.
- `--kernel NAME`: kernel profile or explicit kernel package name.
- `--bootloader NAME`: bootloader profile from `configs/bootloaders/`.
- `--package-profile NAME`: additional package profile from `configs/packages/`.
- `--service-profile NAME`: additional service profile from `configs/services/`.
- `--live-profile NAME`: live-user preset from `configs/live-users/`.
- `--live-user NAME`: live username override.
- `--live-groups a,b,c`: live-user group override.

## Configuration Model

The effective configuration is assembled from multiple layers:

1. `configs/global_build.json`
2. `configs/architectures/<arch>.json`
3. Optional desktop profile
4. Optional kernel profile
5. Optional bootloader profile
6. Optional package profiles
7. Optional service profiles
8. Optional live-user profile
9. CLI overrides such as `--live-user` and `--live-groups`

The merge process is implemented in `core.config_loader.ConfigAssembler`.

## Main Components

- `cli.py`: command-line entrypoint.
- `core/orchestrator.py`: top-level workflow controller.
- `core/config_loader.py`: layered config assembly and merge logic.
- `core/iso_engine.py`: engine and final ISO build flow.
- `core/chroot_manager.py`: chroot command execution and package installation.
- `core/toolchain.py`: isolated build-host bootstrap and tool execution.
- `core/customizer.py`: applies users, services, files, locale, mkinitcpio, and related customizations.

## Testing

Run the full test suite:

```bash
python3 -m unittest discover -s tests
```

Quick syntax verification:

```bash
python3 -m py_compile cli.py core/*.py
```

## Sphinx Documentation

Additional complete documentation is available under `docs/`.

Install documentation dependencies:

```bash
python3 -m pip install -r docs/requirements.txt
```

Build HTML docs:

```bash
make -C docs html
```

Or directly:

```bash
python3 -m sphinx -b html docs docs/_build/html
```

## Troubleshooting

## Build falls back from configured workdir

If the configured workdir is not writable, Arch-Builder automatically falls back to:

```text
arch-builder/fallback/<architecture>/
```

## Real build fails on a non-Arch host

Use:

```bash
sudo python3 cli.py x86_64 --mode real --force-isolated-toolchain
```

## pacman bootstrap is flaky or slow

Use retries and diagnostics:

```bash
sudo python3 cli.py x86_64 --mode real --toolchain-debug --toolchain-pacman-retries 4
```

## License and Status

This repository currently focuses on implementation and operational documentation. If licensing, packaging, or CI publication are needed, add them explicitly to the repository policy.