# CLI Reference

The main entrypoint is `cli.py`.

## Syntax

```bash
python3 cli.py [architecture] [options]
```

## Core arguments

- `architecture`: target architecture, default `x86_64`; supported engines are `x86_64` and `aarch64`.
- `--device NAME`: hardware profile (`rpi4`, `odroid-n2`, `pinebookpro`, `rockpro64`, or `generic-uefi`).
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

- `-o, --output PATH`: explicit ISO or disk-image output path.

When omitted, the output name is generated automatically using desktop and architecture. ISO builds use `.iso`; device/disk builds use `.img`. SHA256 (`.sha256`) and MD5 (`.md5`) checksum files are generated alongside the final artifact.

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

## ARM board image

```bash
sudo python3 cli.py --device rpi4 --mode real --format img --desktop xfce
sudo python3 cli.py --device odroid-n2 --mode real --format img --desktop xfce
```

## Virtual machine disks

Disk builds can be converted directly with `qemu-img`. VM formats are left uncompressed:

```bash
sudo python3 cli.py x86_64 --mode real --format vdi --desktop xfce
sudo python3 cli.py x86_64 --mode real --format vmdk --desktop xfce
```

The resulting `.vdi` or `.vmdk` files are written to `output/` alongside their checksums.
