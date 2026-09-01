# Package And Service Profiles

This page documents every JSON file under `configs/software/` and `configs/services/`.

## Package profiles

Package profiles usually provide either:

- a `packages` list for feature bundles, or
- `package_sources` for official, local, or AUR package acquisition

| File | Purpose | Notable contents |
| --- | --- | --- |
| `configs/software/audio.json` | PipeWire-based audio stack. | `pipewire`, `pipewire-alsa`, `pipewire-pulse`, `wireplumber`, `alsa-utils`, `pavucontrol`. |
| `configs/software/base.json` | Core package set for the live ISO. | `base`, `linux`, `linux-firmware`, `vim`, `networkmanager`, `7zip`. |
| `configs/software/bluetooth.json` | Bluetooth support bundle. | `bluez`, `bluez-utils`, `blueman`. |
| `configs/software/containers.json` | Container tooling profile. | `docker`, `docker-compose`, `podman`, `buildah`. |
| `configs/software/custom-user.json` | Local package sourcing profile. | Local package dir `configs/custom-packages/local`. |
| `configs/software/aur-packages.json` | Custom AUR packages profile. | `yay-bin`, `pamac-aur`. |
| `configs/software/dev-tools.json` | General development toolchain. | `base-devel`, `git`, `cmake`, `ninja`, `make`, `gcc`, `gdb`, `ripgrep`. |
| `configs/software/display-manager.json` | SDDM display-manager bundle. | `sddm`. |
| `configs/software/filesystems.json` | Filesystem tooling bundle. | `btrfs-progs`, `xfsprogs`, `exfatprogs`, `dosfstools`, `ntfs-3g`. |
| `configs/software/fonts-locales.json` | Fonts and locale coverage. | `noto-fonts`, `noto-fonts-cjk`, `noto-fonts-emoji`, `ttf-dejavu`, `glibc`. |
| `configs/software/monitoring.json` | Monitoring and diagnostics utilities. | `htop`, `iotop`, `btop`, `sysstat`, `lsof`. |
| `configs/software/multimedia.json` | Multimedia codecs and playback. | `ffmpeg`, `vlc`, `gst-plugins-base`, `gst-plugins-good`, `gst-plugins-bad`. |
| `configs/software/network-advanced.json` | Advanced networking and firewall set. | `networkmanager`, `nm-connection-editor`, `openssh`, `wireguard-tools`, `nmap`, `tcpdump`, `ufw`. |
| `configs/software/networking.json` | Wireless and DNS compatibility profile. | `iwd`, `wpa_supplicant`, `openresolv`. |
| `configs/software/node-dev.json` | Node.js developer profile. | `nodejs`, `npm`, `yarn`, `pnpm`. |
| `configs/software/printing.json` | Printing stack. | `cups`, `cups-pdf`, `system-config-printer`, `ghostscript`. |
| `configs/software/python-dev.json` | Python developer profile. | `python`, `python-pip`, `python-virtualenv`, `python-setuptools`, `ipython`. |
| `configs/software/security.json` | Security and hardening toolkit. | `iptables`, `nftables`, `fail2ban`, `lynis`, `clamav`. |
| `configs/software/calamares-installer.json` | Installer profile using the bundled local package. | Calamares local package plus filesystem and partitioning tools. |
| `configs/software/virtualization.json` | KVM and virtualization stack. | `qemu-full`, `libvirt`, `virt-manager`, `dnsmasq`, `edk2-ovmf`. |
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
| `configs/services/common-remote.json` | Remote access service. | `sshd` |
| `configs/services/common-virtualization.json` | Virtualization daemons. | `libvirtd`, `virtlogd.socket` |

### Example use

```bash
python3 cli.py x86_64 --service-profile common-base --service-profile common-printing
python3 cli.py x86_64 --service-profile common-remote
```
