# Customizer Actions

This page documents the action categories implemented by `core.customizer.SystemConfigurator`.

The configurator converts merged config data into an ordered action list and applies that list against the active chroot.

## Execution model

<pre class="mermaid">
flowchart TD
    CFG[Merged config] --> LOAD[SystemConfigurator.load_from_config]
    LOAD --> ACTS[Action list]
    ACTS --> OVERLAY[OverlayAction]
    ACTS --> LOCALE[LocaleAction]
    ACTS --> USER[UserAction]
    ACTS --> SERVICE[ServiceAction]
    ACTS --> CMD[CommandAction]
    ACTS --> INIT[ MkinitcpioAction ]
    ACTS --> FILE[FileAction]
    ACTS --> APPLY[SystemConfigurator.apply]
</pre>

## Action ordering

The configurator loads actions in a deliberate order:

1. overlay application
2. locale, hostname, timezone, and keymap setup
3. user creation
4. service enablement
5. generic post-install commands
6. `mkinitcpio` generation config
7. explicit file copies

This keeps broad filesystem overlays early and targeted adjustments later.

## `OverlayAction`

- Purpose: copy an entire overlay tree into the target rootfs.
- Source key: `customizations.overlay_dir` or `system_config.overlay_dir`.
- Real mode behavior: copies the overlay directly onto the active chroot path.
- Mock mode behavior: logs the simulated overlay application.

Use this when a whole directory tree should behave like an `airootfs` layer.

## `LocaleAction`

- Purpose: apply hostname, timezone, locale, and virtual console keymap.
- Source keys: `customizations.hostname`, `timezone`, `locale`, `keymap`.
- Real mode actions:
  - writes `/etc/hostname`
  - links `/etc/localtime`
  - enables the chosen locale in `/etc/locale.gen`
  - runs `locale-gen`
  - writes `/etc/locale.conf`
  - writes `/etc/vconsole.conf`

This is the central locale and identity action for the live system.

## `UserAction`

- Purpose: create live or target users and configure their privileges.
- Source key: `customizations.users`.
- Real mode actions:
  - creates missing groups first
  - creates the user with `/bin/bash`
  - sets passwords through `chpasswd`
  - enables `wheel` sudo privileges when applicable

Important behavior:

- Group creation is automatic, which avoids failures when custom profiles reference groups not yet present in the target image.
- Users in `wheel` automatically get sudo enabled in `/etc/sudoers`.

## `ServiceAction`

- Purpose: enable systemd units inside the target system.
- Source key: `customizations.services`.
- Compatibility fallback: `platform_specific.services` when the main customization list is empty.
- Real mode behavior: runs `systemctl enable <service>` inside the chroot.

Use service profiles when you want reusable bundles of enablement decisions.

## `CommandAction`

- Purpose: run arbitrary commands in the target chroot.
- Source key: `customizations.commands` or `system_config.commands`.
- Real mode behavior: delegates directly to `chroot.run_command()`.

This is the escape hatch for post-install tasks that do not justify a dedicated action class.

## `MkinitcpioAction`

- Purpose: generate a deterministic `/etc/mkinitcpio.conf` suited to live ISO boot.
- Source key: `platform_specific.initramfs_config`.
- Managed fields:
  - `modules`
  - `binaries`
  - `files`
  - `hooks`

Real mode writes the config file directly into the active chroot rootfs rather than trying to copy a host-side file later.

This is important for live boot because hooks like `archiso`, `archiso_loop_mnt`, and `memdisk` must be present and ordered correctly.

## `FileAction`

- Purpose: copy a single file into a target path in the chroot.
- Source key: `customizations.files` or `system_config.files`.
- Managed fields:
  - `src`
  - `dest`
  - optional `mode`

Real mode behavior:

- ensures the destination directory exists
- copies the file from the host workspace into the active chroot path
- optionally applies file permissions with `chmod`

Use this for explicit, narrow file placement when a full overlay would be excessive.

## `SystemConfigurator.apply()` behavior

`apply()` performs the already-loaded action list against the current `ChrootManager`.

Operational notes:

- if no chroot is provided, the configurator logs a warning and does nothing
- if no actions are queued, it logs that nothing is pending
- action failures are logged individually, which helps preserve context during debugging

## Config sources that feed these actions

The main inputs come from:

- `customizations`
- `system_config`
- `platform_specific.initramfs_config`

For concrete examples, see the profile catalog under [profiles/index](../profiles/index.md).