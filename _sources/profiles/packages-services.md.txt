# Package And Service Profiles

This page documents every JSON file under `configs/software/` and `configs/services/`.

## Package profiles

Package profiles usually provide either:

- a `packages` list for feature bundles, or
- `package_sources` for official, local, or AUR package acquisition

| File | Purpose | Notable contents |
| --- | --- | --- |
| `configs/software/audio.json` | PipeWire-based audio stack. | `pipewire`, `pipewire-alsa`, `pipewire-pulse`, `wireplumber`, `alsa-utils`, `pavucontrol`. |
| `configs/software/base.json` | Minimal essential package set. | `base`, `linux`, `efuse`, `vim`, `networkmanager`; dependency on `pacman`. |
| `configs/software/bluetooth.json` | Bluetooth support bundle. | `bluez`, `bluez-utils`, `blueman`. |
| `configs/software/containers.json` | Container tooling profile. | `docker`, `docker-compose`, `podman`, `buildah`. |
| `configs/software/custom-user.json` | Mixed official/local/AUR package sourcing example. | Official `calamares`, local package dir `configs/custom-packages/local`, AUR `calamares-git`. |
| `configs/software/aur-packages.json` | Custom AUR packages profile. | `yay-bin`, `pamac-aur`. |
| `configs/software/dev-tools.json` | General development toolchain. | `base-devel`, `git`, `cmake`, `ninja`, `make`, `gcc`, `gdb`, `ripgrep`. |
| `configs/software/display-manager.json` | Display-manager helper bundle. | `sddm`, `xf86-video-intel`. |
| `configs/software/filesystems.json` | Filesystem tooling bundle. | `btrfs-progs`, `xfsprogs`, `exfatprogs`, `dosfstools`, `ntfs-3g`. |
| `configs/software/fonts-locales.json` | Fonts and locale coverage. | `noto-fonts`, `noto-fonts-cjk`, `noto-fonts-emoji`, `ttf-dejavu`, `glibc`. |
| `configs/software/monitoring.json` | Monitoring and diagnostics utilities. | `htop`, `iotop`, `btop`, `sysstat`, `lsof`. |
| `configs/software/multimedia.json` | Multimedia codecs and playback. | `ffmpeg`, `vlc`, `gst-plugins-base`, `gst-plugins-good`, `gst-plugins-bad`. |
| `configs/software/network-advanced.json` | Advanced networking and firewall set. | `networkmanager`, `nm-connection-editor`, `openssh`, `wireguard-tools`, `nmap`, `tcpdump`, `ufw`. |
| `configs/software/networking.json` | Basic networking profile. | `netctl`, `resolvconf`. |
| `configs/software/node-dev.json` | Node.js developer profile. | `nodejs`, `npm`, `yarn`, `pnpm`. |
| `configs/software/printing.json` | Printing stack. | `cups`, `cups-pdf`, `system-config-printer`, `ghostscript`. |
| `configs/software/python-dev.json` | Python developer profile. | `python`, `python-pip`, `python-virtualenv`, `python-setuptools`, `ipython`. |
| `configs/software/security.json` | Security and hardening toolkit. | `iptables-nft`, `nftables`, `fail2ban`, `lynis`, `clamav`. |
| `configs/software/systemd.json` | systemd-focused package bundle. | `systemd`, `systemd-boot`. |
| `configs/software/virtualization.json` | KVM and virtualization stack. | `qemu-full`, `libvirt`, `virt-manager`, `dnsmasq`, `bridge-utils`, `edk2-ovmf`. |
| `configs/software/wayland.json` | Wayland session support. | `wayland`, `xorg-xwayland`, `wl-clipboard`, `grim`, `slurp`. |
| `configs/software/xorg.json` | X11/Xorg stack. | `xorg-server`, `xorg-xinit`, `xorg-xrandr`, `xorg-xset`, `xorg-xinput`. |

### Example use

```bash
python3 cli.py x86_64 --package-profile audio --package-profile multimedia
python3 cli.py x86_64 --package-profile dev-tools --package-profile python-dev
python3 cli.py x86_64 --package-profile custom-user
```

## Service profiles

Service profiles generally populate `customizations.services` with systemd units to enable in the target image.

| File | Purpose | Services |
| --- | --- | --- |
| `configs/services/common-base.json` | Core runtime services. | `NetworkManager`, `systemd-timesyncd` |
| `configs/services/common-bluetooth.json` | Bluetooth runtime services. | `bluetooth` |
| `configs/services/common-printing.json` | Printing services. | `cups` |
| `configs/services/common-remote.json` | Remote access and discovery. | `sshd`, `avahi-daemon` |
| `configs/services/common-virtualization.json` | Virtualization daemons. | `libvirtd`, `virtlogd` |

### Example use

```bash
python3 cli.py x86_64 --service-profile common-base --service-profile common-printing
python3 cli.py x86_64 --service-profile common-remote
```
