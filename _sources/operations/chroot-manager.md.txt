# Chroot Manager

This page documents the operational responsibilities of `core.chroot_manager.ChrootManager`.

The chroot manager is the execution boundary for package installation, chroot command invocation, and simple target filesystem tasks.

## Core modes

The manager supports two modes:

- `mock`: simulation-oriented behavior for tests and development
- `real`: actual command execution through `sudo chroot`

## Lifecycle overview

<pre class="mermaid">
flowchart TD
    INIT[ChrootManager init] --> SETUP[setup]
    SETUP --> RUN[run_command]
    RUN --> PKG[install_packages]
    RUN --> FSTAB[generate_fstab]
    PKG --> OFF[official packages]
    PKG --> LOCAL[local package files]
    PKG --> AUR[AUR packages]
</pre>

## Construction

`ChrootManager` accepts either:

- `workdir`
- `chroot_path`

One of them must be present. The resolved path becomes the active chroot root.

## `setup()`

- Mock mode: logs virtual setup and returns the workdir.
- Real mode: creates the underlying chroot directory on disk.

This method is intentionally minimal because most higher-order orchestration happens in the toolchain and ISO builder layers.

## `run_command()`

`run_command()` is the central execution primitive.

Behavior:

- accepts either a shell string or a list of command arguments
- in mock mode, returns simulated output and logs intent
- in real mode, executes with `sudo chroot <effective_chroot> ...`

Important detail:

- the `effective_chroot` is taken from the explicit `chroot_path` argument when provided, otherwise it uses the manager's configured workdir

This is what lets orchestration redirect real-mode package and system operations into the isolated bootstrap rootfs when needed.

## Package installation flow

`install_packages()` normalizes either a plain package list or a structured package plan.

The normalized plan includes:

- `official`
- `aur`
- `local_paths`

### Official packages

Handled by `_install_official_packages_real()`.

Behavior:

- installs with `pacman -S --needed --noconfirm`
- retries failures up to a fixed attempt count
- refreshes package databases with `pacman -Syy` between attempts when necessary

### Local packages

Handled by `_install_local_packages_real()`.

Behavior:

- copies local package files into `<chroot>/tmp/custom-packages`
- installs them with `pacman -U --noconfirm`

### AUR packages

Handled by `_install_aur_packages_real()`.

Behavior:

- installs `git` and `base-devel`
- creates a non-root `aurbuilder` user if absent
- clones AUR repos under `/tmp`
- builds packages with `makepkg -si`

Safety detail:

- package names are validated through a conservative regex before being used in the build command

## `generate_fstab()`

- Mock mode: writes a simulated `/etc/fstab` via the mock filesystem handler
- Real mode: currently uses a placeholder command path and returns logged output

This keeps tests deterministic while leaving room for a more hardware-aware real implementation later.

## Mock filesystem support

`MockFSHandler` supports simulated:

- file creation
- file reads
- directory listing

This is mainly for unit and integration-style testing, where executing real privileged filesystem operations would be inappropriate.

## Failure model

The manager raises:

- `ChrootManagerError`
- `ChrootError` as a backward-compatible alias

These errors are used by the higher orchestration layers to surface actionable failures without losing the command context.

## Practical role in the whole build

The chroot manager does not decide what the system should contain. It provides the execution substrate for:

- package operations
- file generation inside the target system
- service enablement
- shell commands needed by customization

The decision-making remains in config assembly, orchestration, and customization layers.