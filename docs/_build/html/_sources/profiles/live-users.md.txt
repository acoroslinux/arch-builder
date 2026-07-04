# Live-User Profiles

This page documents every JSON file under `configs/live-users/`.

These profiles define the interactive live-session user and can be combined with display-manager autologin alignment performed by the configuration assembler.

| File | Purpose | Username | Groups | Notes |
| --- | --- | --- | --- | --- |
| `configs/live-users/live.json` | Default live-user profile. | `live` | `wheel`, `video`, `audio`, `networkmanager` | General-purpose default. |
| `configs/live-users/live-admin.json` | Elevated live-user preset. | `liveadmin` | `wheel`, `video`, `audio`, `networkmanager`, `storage` | Useful when admin-like live sessions need storage access. |
| `configs/live-users/live-minimal.json` | Minimal-permission profile. | `live` | `audio`, `video` | Excludes `wheel` and `networkmanager`. |
| `configs/live-users/x86_64-live.json` | x86_64-tailored live-user preset. | `live` | `wheel`, `video`, `audio`, `networkmanager` | Mirrors the standard desktop-friendly x86_64 setup. |
| `configs/live-users/i386-live.json` | i386-tailored live-user preset. | `live32` | `wheel`, `audio`, `networkmanager` | Lighter group set for 32-bit builds. |
| `configs/live-users/aarch64-live.json` | aarch64 live-user preset. | `livearm` | `wheel`, `audio`, `video`, `networkmanager` | ARM-friendly naming. |
| `configs/live-users/arm64-live.json` | arm64 alias live-user preset. | `livearm` | `wheel`, `audio`, `video`, `networkmanager` | Parallel preset for `arm64` naming. |

## Example use

```bash
python3 cli.py x86_64 --live-profile live-admin
python3 cli.py i386 --live-profile i386-live
python3 cli.py x86_64 --live-user demo --live-groups wheel,audio,video
```