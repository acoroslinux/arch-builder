# System Foundation Profiles

This page documents the JSON files that define the core build substrate: global defaults, architecture layers, bootloaders, and kernels.

## Global manifest

### `configs/global_build.json`

- Purpose: master manifest for build defaults and shared binary paths.
- Important keys: `metadata`, `system`, `system_config`.
- Notable values: workspace-local workdir/cache paths and ISO/disk output under `output/`.
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
| `configs/architectures/aarch64.json` | ARM64 board foundation. | Raspberry Pi 4, ODROID-N2, PineBook Pro and RockPro64 target metadata; board selection comes from `--device`. |

## Hardware profiles

Hardware profiles live under `configs/hardware/` and select the architecture, bootloader and output format. Use them with `--device`; do not combine an ARM device with `x86_64`-only local packages. `visionfive2` and `asahi` remain placeholders and are rejected for real builds.

### Example use

```bash
python3 cli.py x86_64
```

## Bootloader profiles

| File | Purpose | Important keys | Notable items |
| --- | --- | --- | --- |
| `configs/boot/grub.json` | GRUB-based bootloader profile. | `platform_specific.packages`, `system.binaries` | Adds `grub` and `efibootmgr`; pins `grub-mkrescue` paths. |
| `configs/boot/syslinux.json` | Syslinux/Isolinux profile for BIOS-style flows. | `platform_specific.packages` | Adds `syslinux`, `mtools`, `dosfstools`. |

### Example use

```bash
python3 cli.py x86_64 --bootloader grub
python3 cli.py x86_64 --bootloader syslinux
```

## Kernel profiles

Kernel files primarily override `platform_specific.base_kernel` and initramfs naming.

| File | Purpose | Notable values |
| --- | --- | --- |
| `configs/system/linux.json` | Default stable kernel. | `base_kernel: linux`, `initramfs-linux.img` |
| `configs/system/linux-lts.json` | Long-term support kernel. | `base_kernel: linux-lts`, `initramfs-linux-lts.img` |
| `configs/system/linux-zen.json` | Performance-oriented desktop kernel. | `base_kernel: linux-zen`, `initramfs-linux-zen.img` |
| `configs/system/linux-hardened.json` | Security-focused kernel variant. | `base_kernel: linux-hardened`, `initramfs-linux-hardened.img` |

### Example use

```bash
python3 cli.py x86_64 --kernel linux-lts
python3 cli.py x86_64 --kernel linux-zen
```
