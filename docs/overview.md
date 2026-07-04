# Overview

Arch-Builder builds customized Arch Linux ISO images from composable JSON profiles.
It is designed around a clear separation of concerns:

- configuration assembly
- build orchestration
- chroot/package execution
- customization application
- bootloader generation
- final ISO packaging

## Architecture At A Glance

<pre class="mermaid">
flowchart LR
	CLI[cli.py] --> ORCH[BuildOrchestrator]
	ORCH --> ASSEMBLER[ConfigAssembler]
	ORCH --> CHROOT[ChrootManager]
	ORCH --> TOOLCHAIN[ToolchainManager]
	ORCH --> BUILDER[ISOBuilder]
	ASSEMBLER --> CONFIGS[configs/*.json]
	BUILDER --> ENGINE[ArchEngine]
	ENGINE --> CUSTOMIZER[SystemConfigurator]
	ENGINE --> ISO[Final ISO]
	TOOLCHAIN --> CACHE[Reusable pacman cache]
</pre>

## Goals

- Support repeatable ISO generation from a workspace-local build tree.
- Allow real builds on non-Arch Linux systems through an isolated Arch toolchain.
- Keep configuration modular so architecture, desktop, kernel, service, and live-user choices can be combined.
- Keep cache reusable across runs while allowing deterministic pre-build cleanup.

## Core Execution Modes

## Mock mode

`mock` mode simulates the build process and is intended for:

- fast development loops
- test execution
- validating configuration assembly and workflow control without root access

## Real mode

`real` mode performs the actual build flow, including package installation and ISO generation.
It can either use host tooling or bootstrap an isolated Arch build host.

## Default Workspace Layout

The default visible build paths are:

```text
arch-builder/
├── cache/pacman/pkg/
├── fallback/
└── workdir/
```

## Profile Composition Model

<pre class="mermaid">
flowchart TD
	G[global_build.json] --> E[Effective configuration]
	A[architectures/<arch>.json] --> E
	D[desktops/<desktop>.json] --> E
	K[kernels/<kernel>.json] --> E
	B[bootloaders/<bootloader>.json] --> E
	P[packages/*.json] --> E
	S[services/*.json] --> E
	L[live-users/*.json] --> E
	C[CLI overrides] --> E
</pre>

## Profile Types

The configuration tree is split by responsibility:

- `architectures/`: platform-specific defaults such as architecture and base packages.
- `desktops/`: desktop packages and display-manager configuration.
- `kernels/`: alternate kernel selections.
- `bootloaders/`: bootloader-specific data.
- `packages/`: reusable package bundles.
- `services/`: reusable service bundles.
- `live-users/`: live-user presets.
- `custom_files/`: files copied into the target filesystem.
- `templates/`: bootloader templates and related assets.