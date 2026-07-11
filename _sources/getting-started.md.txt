# Getting Started

## Requirements

- Linux host
- Python 3.10 or newer
- root privileges for `--mode real`

## Repository Setup

Clone the repository and run commands from the project root.

## Discover available profiles

```bash
python3 cli.py --list-options
```

## First mock build

```bash
python3 cli.py x86_64 --desktop xfce
```

This will use a dynamic ISO output name unless `-o` is provided.

## First real build

```bash
sudo python3 cli.py x86_64 --mode real --desktop xfce --force-isolated-toolchain
```

## Useful build options

- `--clean`: start from a cleaned build tree.
- `--no-clean`: reuse previous build state.
- `--toolchain-debug`: write detailed isolated-toolchain diagnostics.
- `--toolchain-pacman-retries N`: increase retry count for bootstrap package operations.

## Output naming

If `-o` is omitted, the output file becomes:

```text
arch-builder-<desktop>-<architecture>.iso
```

If no desktop override is supplied, `base` is used in the generated name.