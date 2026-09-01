# Build Hooks

Optional shell hooks are grouped by phase under `configs/hooks/`:

- `pre_build`: host preparation before the pipeline starts.
- `pre_chroot`: host preparation immediately before target-root creation.
- `post_chroot`: target-root actions immediately after rootfs creation.
- `pre_packages`: host preparation immediately before package installation.
- `post_packages`: target-root actions after package installation.
- `pre_customize`: target-root actions before configuration overlays.
- `post_customize`: target-root actions after overlays and customization.
- `pre_boot`: target-root actions before boot image generation.
- `pre_iso`: host actions before ISO/disk packaging.
- `post_iso`: host actions after ISO/disk packaging.
- `post_build`: host cleanup or artifact processing after the artifact is created.

Only non-symlink `*.sh` files are executed, in lexical order. Target-root
hooks run inside the chroot and receive `CHROOT_PATH`, `WORK_DIR`, `ARCH`,
`DISTRO`, `FORMAT`, and `HOOK_PHASE` environment variables. Host hooks receive
the same metadata and run with the repository as their working directory.

Hooks are optional; missing phase directories are ignored.
