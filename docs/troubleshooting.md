# Troubleshooting

## Workdir not writable

If the configured workdir cannot be written, Arch-Builder falls back to:

```text
arch-builder/fallback/<architecture>/
```

Check repository permissions and available space if fallback usage is unexpected.

## `/tmp` is too small

The project is designed to build in the workspace-local paths under `arch-builder/`, not in `/tmp`, except for temporary tool outputs used internally by upstream tooling.

## Non-Arch host missing `pacman`

Run the real build with isolated bootstrap:

```bash
sudo python3 cli.py x86_64 --mode real --force-isolated-toolchain
```

## pacman cache should be reusable

The persistent cache is outside the target chroot tree under:

```text
arch-builder/cache/pacman/pkg/
```

If packages are downloaded repeatedly, verify this path is writable and not being removed externally.

## Build state should be preserved between runs

Use:

```bash
python3 cli.py x86_64 --no-clean
```

## Bootstrap package operations are flaky

Increase retries and enable diagnostics:

```bash
sudo python3 cli.py x86_64 --mode real --toolchain-debug --toolchain-pacman-retries 4
```

## Diagnostics log location

By default, diagnostics are written inside the active workdir unless overridden with `--toolchain-debug-log`.

## Bootloader or final ISO generation fails

Check:

- configured binary paths in `configs/global_build.json`
- real build permissions
- presence of generated files under the active workdir or fallback tree
- toolchain debug log when isolated mode is enabled