# Profile Catalog

This section documents every JSON profile under `configs/`.

Use it as the reference layer for understanding what each profile contributes to the effective build configuration.

```{toctree}
:maxdepth: 2

system-foundation
desktops
live-users
packages-services
assets-and-templates
```

## Reading Strategy

- Start with `global_build.json` for project-wide defaults.
- Then read the architecture profile for platform behavior.
- Add one desktop profile, optional kernel and bootloader profiles, and any package/service/live-user overlays.
- Finish with CLI overrides when a build needs per-run customization.