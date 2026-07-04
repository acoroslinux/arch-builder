# Isolated Build Troubleshooting

This page focuses on failure modes that were actually encountered while stabilizing real isolated builds.

Use it together with the general guide in [troubleshooting](troubleshooting.md).

## Quick diagnosis checklist

When a real isolated build fails, check these first:

1. Are you running with `sudo` for `--mode real`?
2. Is the workspace path writable by the current user?
3. Is `arch-builder/cache/pacman/pkg/` writable and reusable?
4. Did you enable `--toolchain-debug` and capture a diagnostics log?
5. Are you forcing isolated mode with `--force-isolated-toolchain` when the host lacks Arch tooling?

Recommended debug command:

```bash
sudo python3 cli.py x86_64 \
  --mode real \
  --force-isolated-toolchain \
  --toolchain-debug \
  --toolchain-debug-log arch-builder/toolchain-debug.log \
  --toolchain-pacman-retries 4
```

## Symptom: host is not Arch and required tools are missing

Typical signal:

- missing `pacman`, `grub-mkrescue`, `genisoimage`, `xorriso`, or `mksquashfs`

Current handling:

- the toolchain checks for host tools
- if they are absent, it bootstraps an isolated Arch rootfs
- you can also force this path with `--force-isolated-toolchain`

Fix:

```bash
sudo python3 cli.py x86_64 --mode real --force-isolated-toolchain
```

## Symptom: diagnostics log path is not writable

Typical signal:

- permission denied while writing the requested toolchain log path

Current handling:

- the toolchain falls back to a log inside the build-host directory

What to do:

- point `--toolchain-debug-log` to a writable workspace path
- or inspect the fallback log under the active workdir/build-host area

## Symptom: `/tmp` does not have enough space

Historical issue:

- relying on `/tmp` for major build state led to storage failures on constrained systems

Current handling:

- main build state is workspace-local under `arch-builder/`
- persistent pacman cache is outside the target chroot
- only limited temporary upstream outputs may still use `/tmp`

What to do:

- keep the workspace on a filesystem with enough free space
- avoid placing the repository itself on a tiny temporary volume

## Symptom: `pacman` reports not enough free disk space inside the isolated chroot

Historical cause:

- `CheckSpace` inside bootstrap environments can produce false negatives when mount layout does not map cleanly to the running namespace

Current handling:

- the toolchain patches `pacman.conf`
- `CheckSpace` is removed
- `CacheDir` is normalized to the bind-mounted reusable cache

What to inspect:

- the generated `pacman.conf` inside the isolated rootfs
- whether the cache bind mount succeeded

## Symptom: repeated package downloads and poor reuse between runs

Historical cause:

- cache living inside the chroot was lost or recreated too often

Current handling:

- package cache is bind-mounted from `arch-builder/cache/pacman/pkg/`

What to do:

- ensure the cache path exists and is writable
- avoid external cleanup of `arch-builder/cache/pacman/pkg/`

## Symptom: mirror or package operations are flaky

Historical cause:

- unstable mirrors or transient metadata failures during bootstrap

Current handling:

- curated mirrorlist with stable mirrors first
- `DisableDownloadTimeout`
- retry logic for both `pacman-key` and `pacman`
- extra `pacman -Syy` refreshes between retries

What to do:

- raise `--toolchain-pacman-retries`
- keep diagnostics enabled for failed attempts

## Symptom: chroot commands run in the wrong rootfs

Historical cause:

- real-mode chroot operations were not always routed to the isolated toolchain rootfs

Current handling:

- orchestration rebinds the effective `ChrootManager` to the toolchain bootstrap root when present
- `run_command()` respects the effective chroot path

What to inspect:

- orchestration logs showing the selected toolchain chroot path
- whether the active rootfs contains the expected `/etc`, `/boot`, and `/var/cache/pacman/pkg`

## Symptom: customization fails on missing groups or initramfs config placement

Historical causes:

- user groups referenced by profiles did not always exist yet
- `mkinitcpio` config handling was too indirect for the active rootfs

Current handling:

- user actions create missing groups before `useradd`
- `mkinitcpio.conf` is written directly into the active chroot rootfs

## Symptom: bootloader creation fails

Historical causes:

- incomplete `grub-mkrescue` invocation
- wrong source directory resolution for `/boot`

Current handling:

- bootloader generation resolves the effective boot source directory from the active chroot when possible
- GRUB invocation includes the output parameter correctly

What to inspect:

- configured GRUB binary path in `configs/global_build.json`
- generated boot directory inside the active chroot or fallback path

## Symptom: final ISO packaging fails or the ISO is left inside the isolated rootfs

Historical cause:

- final packaging path handling was incorrect for isolated mode

Current handling:

- if the rescue ISO exists inside the isolated chroot, the builder copies it out to the requested destination path

What to inspect:

- `<isolated-root>/tmp/bootloader-rescue.iso`
- requested final output path

## Symptom: cleanup prints noisy unmount warnings

Historical cause:

- best-effort `umount` calls emitted expected noise for already-unmounted targets

Current handling:

- cleanup unmounts use non-check mode with suppressed stdout/stderr where the warnings are not actionable

## Symptom: workspace-local fallback path becomes unwritable after `sudo` builds

Historical cause:

- a visible build directory such as `arch-builder/` can become root-owned after real-mode execution

Current handling:

- the builder first tries the workspace-local fallback path
- if that is not writable, it degrades to `/tmp/arch-builder-fallback/<arch>/`

What to do:

- if you want the workspace path back, fix ownership explicitly, for example:

```bash
sudo chown -R "$USER":"$USER" arch-builder
```

## Recommended recovery workflow

1. rerun with `--toolchain-debug`
2. inspect the toolchain log
3. verify write permissions on `arch-builder/` and the cache path
4. retry with a higher pacman retry count
5. if ownership is polluted by previous `sudo` runs, repair ownership and rerun with `--clean`