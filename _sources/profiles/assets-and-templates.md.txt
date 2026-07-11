# Asset And Template Files

This page documents the non-JSON assets that materially affect the generated live system and boot UX.

## `configs/custom_files/`

These files are copied into the target root filesystem when referenced by active profiles.

| File | Target path | Purpose | Notable contents |
| --- | --- | --- | --- |
| `configs/custom_files/etc/vconsole.conf` | `/etc/vconsole.conf` | Console keymap configuration. | `KEYMAP=pt-latin1` |
| `configs/custom_files/etc/skel/.bashrc` | `/etc/skel/.bashrc` | Default shell skeleton for new users. | Adds `~/.local/bin` to `PATH` and defines `ll` alias. |
| `configs/custom_files/etc/lightdm/lightdm.conf` | `/etc/lightdm/lightdm.conf` | LightDM runtime and autologin defaults. | Autologin enabled for `live`, `user-session=xfce`. |
| `configs/custom_files/etc/lightdm/lightdm-gtk-greeter.conf` | `/etc/lightdm/lightdm-gtk-greeter.conf` | GTK greeter theme and panel setup. | Adwaita theme, clock, session, accessibility, and power indicators. |
| `configs/custom_files/etc/gdm/custom.conf` | `/etc/gdm/custom.conf` | GDM autologin and Wayland behavior. | Enables autologin and keeps Wayland enabled. |
| `configs/custom_files/etc/sddm.conf.d/autologin.conf` | `/etc/sddm.conf.d/autologin.conf` | SDDM autologin preset. | Defaults to `User=live`, `Session=plasma.desktop`. |

## Operational notes

- Live-user overrides can later rewrite the autologin target user while preserving the display-manager config structure.
- The LightDM and SDDM files are intentionally generic enough to be reused across multiple desktop profiles.
- If a desktop profile changes its default session name, the matching asset should be reviewed.

## `configs/templates/`

These files are parameterized bootloader templates used during ISO generation.

| File | Boot mode | Purpose | Placeholders |
| --- | --- | --- | --- |
| `configs/templates/grub/grub.cfg.in` | UEFI / GRUB | Generates the GRUB menu and rescue entry. | `@@BOOT_TITLE@@`, `@@ARCH@@`, `@@KERNEL_NAME@@`, `@@KERNEL_FILE@@`, `@@ISO_LABEL@@`, `@@BOOT_CMDLINE@@`, `@@INITRAMFS_FILE@@` |
| `configs/templates/syslinux/syslinux.cfg.in` | BIOS / Syslinux | Generates Syslinux menu, boot entry, rescue entry, reboot, and poweroff actions. | `@@BOOT_TITLE@@`, `@@ARCH@@`, `@@KERNEL_FILE@@`, `@@INITRAMFS_FILE@@`, `@@ISO_LABEL@@`, `@@BOOT_CMDLINE@@` |

## Template behavior details

### `grub.cfg.in`

- Presents a main live entry and a rescue command-line entry.
- Loads video/font modules and switches to `gfxterm`.
- Passes `archisobasedir`, `archisolabel`, and optional boot cmdline values to the kernel.

### `syslinux.cfg.in`

- Uses `vesamenu.c32` for BIOS boot UX.
- Provides live, rescue, reboot, and poweroff menu entries.
- Includes timeout and visual menu settings for a boot splash style menu.

## Maintenance guidance

When changing kernel naming, ISO labels, or boot cmdline assembly logic, review these templates together with the code that performs placeholder substitution.