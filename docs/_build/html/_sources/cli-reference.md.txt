# CLI Reference

The main entrypoint is `cli.py`.

## Syntax

```bash
python3 cli.py [architecture] [options]
```

## Core arguments

- `architecture`: target architecture, default `x86_64`.
- `-c, --config`: global configuration file path.
- `--mode {mock,real}`: build execution mode.

## Build-tree behavior

- `--clean`: remove old build artifacts before starting.
- `--no-clean`: retain existing build artifacts.

## Isolated toolchain

- `--force-isolated-toolchain`: force isolated Arch bootstrap toolchain.
- `--toolchain-debug`: enable detailed diagnostics.
- `--toolchain-debug-log PATH`: override diagnostics log path.
- `--toolchain-pacman-retries N`: configure bootstrap retry count.

## Profile overrides

- `-d, --desktop NAME`
- `-k, --kernel NAME`
- `-b, --bootloader NAME`
- `-p, --package-profile NAME`
- `-s, --service-profile NAME`
- `--live-profile NAME`
- `--live-user NAME`
- `--live-groups group1,group2`

## Metadata and inspection

- `--list-options`: print available profiles from the configuration tree.
- `-v, --verbose`: enable verbose logging.

## Output control

- `-o, --output PATH`: explicit ISO output path.

When omitted, the output name is generated automatically using desktop and architecture.

## Example commands

## Mock build with XFCE

```bash
python3 cli.py x86_64 --desktop xfce
```

## Real build with isolated toolchain and debug logging

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

## Real build reusing previous state

```bash
sudo python3 cli.py x86_64 --mode real --no-clean
```