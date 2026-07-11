# Package And Service Profiles

This page documents every JSON file under `configs/packages/` and `configs/services/`.

## Package profiles

Package profiles usually provide either:

- a `packages` list for feature bundles, or
- `package_sources` for official, local, or AUR package acquisition

| File | Purpose | Notable contents |
| --- | --- | --- |
| `configs/packages/audio.json` | PipeWire-based audio stack. | `pipewire`, `pipewire-alsa`, `pipewire-pulse`, `wireplumber`, `alsa-utils`, `pavucontrol`. |
| `configs/packages/base.json` | Minimal essential package set. | `base`, `linux`, `efuse`, `vim`, `networkmanager`; dependency on `pacman`. |
| `configs/packages/bluetooth.json` | Bluetooth support bundle. | `bluez`, `bluez-utils`, `blueman`. |
| `configs/packages/containers.json` | Container tooling profile. | `docker`, `docker-compose`, `podman`, `buildah`. |
| `configs/packages/custom-user.json` | Mixed official/local/AUR package sourcing example. | Official `calamares`, local package dir `configs/custom-packages/local`, AUR `calamares-git`. |
| `configs/packages/aur-packages.json` | Custom AUR packages profile. | `yay-bin`, `pamac-aur`. |
| `configs/packages/dev-tools.json` | General development toolchain. | `base-devel`, `git`, `cmake`, `ninja`, `make`, `gcc`, `gdb`, `ripgrep`. |
| `configs/packages/display-manager.json` | Display-manager helper bundle. | `sddm`, `xf86-video-intel`. |
| `configs/packages/filesystems.json` | Filesystem tooling bundle. | `btrfs-progs`, `xfsprogs`, `exfatprogs`, `dosfstools`, `ntfs-3g`. |
| `configs/packages/fonts-locales.json` | Fonts and locale coverage. | `noto-fonts`, `noto-fonts-cjk`, `noto-fonts-emoji`, `ttf-dejavu`, `glibc`. |
| `configs/packages/monitoring.json` | Monitoring and diagnostics utilities. | `htop`, `iotop`, `btop`, `sysstat`, `lsof`. |
| `configs/packages/multimedia.json` | Multimedia codecs and playback. | `ffmpeg`, `vlc`, `gst-plugins-base`, `gst-plugins-good`, `gst-plugins-bad`. |
| `configs/packages/network-advanced.json` | Advanced networking and firewall set. | `networkmanager`, `nm-connection-editor`, `openssh`, `wireguard-tools`, `nmap`, `tcpdump`, `ufw`. |
| `configs/packages/networking.json` | Basic networking profile. | `netctl`, `resolvconf`. |
| `configs/packages/node-dev.json` | Node.js developer profile. | `nodejs`, `npm`, `yarn`, `pnpm`. |
| `configs/packages/printing.json` | Printing stack. | `cups`, `cups-pdf`, `system-config-printer`, `ghostscript`. |
| `configs/packages/python-dev.json` | Python developer profile. | `python`, `python-pip`, `python-virtualenv`, `python-setuptools`, `ipython`. |
| `configs/packages/security.json` | Security and hardening toolkit. | `iptables-nft`, `nftables`, `fail2ban`, `lynis`, `clamav`. |
| `configs/packages/systemd.json` | systemd-focused package bundle. | `systemd`, `systemd-boot`. |
| `configs/packages/virtualization.json` | KVM and virtualization stack. | `qemu-full`, `libvirt`, `virt-manager`, `dnsmasq`, `bridge-utils`, `edk2-ovmf`. |
| `configs/packages/wayland.json` | Wayland session support. | `wayland`, `xorg-xwayland`, `wl-clipboard`, `grim`, `slurp`. |
| `configs/packages/xorg.json` | X11/Xorg stack. | `xorg-server`, `xorg-xinit`, `xorg-xrandr`, `xorg-xset`, `xorg-xinput`. |

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