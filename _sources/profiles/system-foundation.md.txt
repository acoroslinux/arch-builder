# System Foundation Profiles

This page documents the JSON files that define the core build substrate: global defaults, architecture layers, bootloaders, and kernels.

## Global manifest

### `configs/global_build.json`

- Purpose: master manifest for build defaults and shared binary paths.
- Important keys: `metadata`, `build_environment`, `system`, `components`.
- Notable values: visible workspace workdir at `arch-builder/workdir`, ISO label `ARCH-MODERN`, binary paths for `grub-mkrescue` and `genisoimage`.
- Use when: changing workspace layout, default binaries, or globally available component declarations.

## Architecture profiles

Common pattern across all architecture files:

- `platform_specific.architecture`
- `platform_specific.base_kernel`
- `platform_specific.initramfs`
- `platform_specific.initramfs_config`
- `platform_specific.packages`
- `customizations` for hostname, locale, keymap, users, and services
- `system_config` for overlay files and post-install commands

| File | Purpose | Notable settings |
| --- | --- | --- |
| `configs/architectures/x86_64.json` | Main 64-bit x86 profile. | Locale `en_US.UTF-8`, timezone `UTC`, keymap `us`, live user with wheel/video/audio/networkmanager. |
| `configs/architectures/i386.json` | 32-bit x86 profile. | Leaner base package set, hostname `arch-builder-i386`, locale `en_US.UTF-8`. |
| `configs/architectures/aarch64.json` | ARM64 profile using the `aarch64` architecture name. | Hostname `arch-builder-arm64`, UTC timezone, standard live user groups. |
| `configs/architectures/arm64.json` | ARM64 alias profile for `arm64`. | Same overall structure as `aarch64`, kept as a separate selectable target. |

### Example use

```bash
python3 cli.py x86_64
python3 cli.py i386
```

## Bootloader profiles

| File | Purpose | Important keys | Notable items |
| --- | --- | --- | --- |
| `configs/bootloaders/grub.json` | GRUB-based bootloader profile. | `platform_specific.packages`, `system.binaries` | Adds `grub` and `efibootmgr`; pins `grub-mkrescue` paths. |
| `configs/bootloaders/syslinux.json` | Syslinux/Isolinux profile for BIOS-style flows. | `platform_specific.packages` | Adds `syslinux`, `mtools`, `dosfstools`. |

### Example use

```bash
python3 cli.py x86_64 --bootloader grub
python3 cli.py x86_64 --bootloader syslinux
```

## Kernel profiles

Kernel files primarily override `platform_specific.base_kernel` and initramfs naming.

| File | Purpose | Notable values |
| --- | --- | --- |
| `configs/kernels/linux.json` | Default stable kernel. | `base_kernel: linux`, `initramfs-linux.img` |
| `configs/kernels/linux-lts.json` | Long-term support kernel. | `base_kernel: linux-lts`, `initramfs-linux-lts.img` |
| `configs/kernels/linux-zen.json` | Performance-oriented desktop kernel. | `base_kernel: linux-zen`, `initramfs-linux-zen.img` |
| `configs/kernels/linux-hardened.json` | Security-focused kernel variant. | `base_kernel: linux-hardened`, `initramfs-linux-hardened.img` |

### Example use

```bash
python3 cli.py x86_64 --kernel linux-lts
python3 cli.py x86_64 --kernel linux-zen
```