# Build Pipeline

This section describes the high-level execution flow.

## Execution Flow Diagram

<pre class="mermaid">
flowchart TD
	START[CLI invocation] --> PARSE[Parse arguments]
	PARSE --> NAME[Resolve output name]
	NAME --> MERGE[Assemble config]
	MERGE --> WORKDIR[Resolve writable workdir]
	WORKDIR --> CHROOT[Create target chroot manager]
	CHROOT --> TOOLCHAIN[Prepare host or isolated toolchain]
	TOOLCHAIN --> PKG[Install packages]
	PKG --> CUSTOM[Apply customizations]
	CUSTOM --> BOOT[Generate bootloader artifacts]
	BOOT --> FINAL[Export final ISO]
</pre>

## 1. CLI parsing

`cli.py` parses user input, resolves a default output name when necessary, and constructs a `BuildOrchestrator`.

## 2. Configuration assembly

`core.config_loader.ConfigAssembler` loads and merges:

- global config
- architecture profile
- optional desktop/kernel/bootloader/package/service/live-user profiles
- CLI live-user overrides

## 3. Workdir resolution

`core.orchestrator.BuildOrchestrator` resolves a writable workspace-local workdir and fallback path.

## 4. Chroot manager setup

`core.chroot_manager.ChrootManager` is initialized against the active target root filesystem.

## 5. Toolchain preparation

`core.toolchain.ToolchainManager` either:

- uses host tools when available, or
- bootstraps an isolated Arch build host in real mode

The isolated toolchain handles:

- bootstrap archive download and extraction
- proc/sys/dev mounts
- package cache bind-mounting
- mirrorlist preparation
- `pacman.conf` adjustments
- `pacman-key` initialization
- installation of build tools such as `archiso`, `xorriso`, and `grub`

## 6. Package installation

The selected engine computes a normalized package plan and installs official packages. Additional customization layers can extend package sets.

## 7. Post-install customization

`core.customizer.SystemConfigurator` applies:

- user creation
- group creation when required
- service enablement
- file copies
- locale and keymap changes
- `mkinitcpio` configuration

## 8. Bootloader generation

The engine runs `grub-mkrescue` or other configured tooling against the prepared rootfs/boot path.

## 9. Final ISO export

The final ISO is either copied out from the isolated chroot or created directly with the configured ISO tooling.

## Cleanup behavior

When `--clean` is active, the builder removes old build artifacts from the active workdir before starting. Reusable cache remains outside the chroot tree.

## Real-Mode Isolation Diagram

<pre class="mermaid">
flowchart LR
	HOST[Host Linux distro] -->|bootstrap if needed| BUILDHOST[Isolated Arch build host]
	BUILDHOST --> ROOTFS[target airootfs]
	CACHE[arch-builder/cache/pacman/pkg] --> BUILDHOST
	ROOTFS --> BOOT[boot artifacts]
	BOOT --> IMAGE[output ISO]
</pre>