# Live-User Profiles

This page documents every JSON file under `configs/live-users/`.

These profiles define the interactive live-session user and can be combined with display-manager autologin alignment performed by the configuration assembler.

| File | Purpose | Username | Groups | Notes |
| --- | --- | --- | --- | --- |
| `configs/live-users/live.json` | Default live-user profile. | `live` | `wheel`, `video`, `audio`, `networkmanager` | General-purpose default. |
| `configs/live-users/live-admin.json` | Elevated live-user preset. | `liveadmin` | `wheel`, `video`, `audio`, `networkmanager`, `storage` | Useful when admin-like live sessions need storage access. |
| `configs/live-users/live-minimal.json` | Minimal-permission profile. | `live` | `audio`, `video` | Excludes `wheel` and `networkmanager`. |
| `configs/live-users/x86_64-live.json` | x86_64-tailored live-user preset. | `live` | `wheel`, `video`, `audio`, `networkmanager` | Mirrors the standard desktop-friendly x86_64 setup. |

## Example use

```bash
python3 cli.py x86_64 --live-profile live-admin
python3 cli.py x86_64 --live-profile x86_64-live
python3 cli.py x86_64 --live-user demo --live-groups wheel,audio,video
```