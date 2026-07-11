# Configuration

Arch-Builder uses JSON files under `configs/` and merges them into a single effective configuration.

## Merge Order

The configuration assembler applies layers in this order:

1. `global_build.json`
2. `architectures/<arch>.json`
3. `desktops/<desktop>.json`
4. `kernels/<kernel>.json`
5. `bootloaders/<bootloader>.json`
6. `packages/<profile>.json`
7. `services/<profile>.json`
8. `live-users/<profile>.json`
9. CLI live-user overrides

Dictionary keys are merged recursively. Lists are extended while avoiding simple duplicates.

## Important top-level areas

## `system`

Contains build runtime settings such as:

- `workdir_base`
- `iso_label`
- tool binary paths
- optional isolated toolchain defaults

## `platform_specific`

Contains architecture-specific data such as:

- `architecture`
- `base_kernel`
- `initramfs`
- package list
- mount layout

## `customizations`

Contains customization intent for:

- hostname
- timezone
- locale
- keymap
- users
- services

## `system_config`

Contains operational customization inputs such as:

- overlay file source tree
- commands to run in the target system
- specific file copy rules

## Live-user profiles

Live-user profiles live under `configs/live-users/`. For example, a profile may define:

- username
- groups
- password

The builder can also align display-manager autologin settings with the resolved live username.

## Custom files

Files under `configs/custom_files/` are copied into the target root filesystem according to explicit rules in configuration.

## Practical approach

Keep `global_build.json` focused on project-wide defaults and use profiles for optional behavior. This keeps builds composable and reduces duplicated package or service definitions.