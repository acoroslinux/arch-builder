# Desktop Profiles

This page documents every desktop JSON profile under `configs/desktops/`.

## Shared structure

Most desktop profiles contribute three things:

- desktop or window-manager packages via `platform_specific.packages`
- a display manager service via `customizations.services`
- display-manager config files through `system_config.files`

Display-manager families:

- LightDM: most X11-oriented desktops and lightweight window managers
- SDDM: KDE, LXQt, Hyprland, Sway, gaming workstation
- GDM: GNOME

| File | Purpose | Display manager | Notable packages and behavior |
| --- | --- | --- | --- |
| `configs/desktops/awesome.json` | Awesome WM profile. | LightDM | `awesome`, `xterm`, `firefox`, `thunar`. |
| `configs/desktops/bspwm.json` | BSPWM tiling setup. | LightDM | `bspwm`, `sxhkd`, `dmenu`, `alacritty`, `thunar`. |
| `configs/desktops/budgie.json` | Budgie desktop session. | LightDM | `budgie-desktop`, `firefox`, `alacritty`. |
| `configs/desktops/cinnamon.json` | Cinnamon desktop. | LightDM | `cinnamon`, `firefox`, `alacritty`. |
| `configs/desktops/gnome.json` | GNOME desktop environment. | GDM | `gnome`, `gnome-tweaks`, `gdm`, custom `/etc/gdm/custom.conf`. |
| `configs/desktops/hyprland.json` | Wayland-first Hyprland profile. | SDDM | `hyprland`, `waybar`, `wofi`, `foot`, `xorg-xwayland`, `xdg-desktop-portal-hyprland`. |
| `configs/desktops/i3.json` | i3 tiling window manager. | LightDM | `i3-wm`, `i3status`, `dmenu`, `alacritty`, `thunar`. |
| `configs/desktops/kde.json` | KDE Plasma desktop. | SDDM | `plasma-meta`, `kde-applications-meta`, `wayland`, `firefox`. |
| `configs/desktops/lxqt.json` | LXQt desktop. | SDDM | `lxqt`, `breeze-icons`, `firefox`, `alacritty`. |
| `configs/desktops/mate.json` | MATE desktop. | LightDM | `mate`, `mate-extra`, `firefox`, `alacritty`. |
| `configs/desktops/openbox.json` | Openbox profile. | LightDM | `openbox`, `obconf`, `tint2`, `alacritty`, `thunar`. |
| `configs/desktops/pantheon.json` | Pantheon desktop. | LightDM | `pantheon`, `firefox`, `alacritty`. |
| `configs/desktops/sway.json` | Wayland Sway compositor profile. | SDDM | `sway`, `swaybg`, `swaylock`, `waybar`, `foot`, `wl-clipboard`. |
| `configs/desktops/wm-minimal.json` | Minimal i3-based environment. | LightDM | `i3-wm`, `i3status`, `dmenu`, `alacritty`, `thunar`, `networkmanager`. |
| `configs/desktops/workstation-gaming.json` | Gaming workstation preset. | SDDM | `plasma-meta`, `steam`, `lutris`, `gamemode`, `mangohud`, `gamescope`, `discord`. |
| `configs/desktops/workstation-office.json` | Office workstation preset. | LightDM | `xfce4`, `xfce4-goodies`, `libreoffice-fresh`, `thunderbird`, `evince`, `file-roller`. |
| `configs/desktops/xfce.json` | XFCE desktop. | LightDM | `xfce4`, `xfce4-goodies`, `firefox`, `alacritty`. |

## Display-manager config files

- LightDM-based profiles commonly inject `lightdm.conf` and `lightdm-gtk-greeter.conf`.
- SDDM-based profiles commonly inject `/etc/sddm.conf.d/autologin.conf`.
- GNOME injects `/etc/gdm/custom.conf`.

## Example use

```bash
python3 cli.py x86_64 --desktop xfce
python3 cli.py x86_64 --desktop workstation-gaming
python3 cli.py x86_64 --desktop hyprland
```