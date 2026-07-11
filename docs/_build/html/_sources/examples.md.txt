# Build Examples

This page collects complete build commands for common scenarios.

## Scenario Map

<pre class="mermaid">
flowchart TD
    BASE[Base live ISO] --> XFCE[Desktop workstation]
    BASE --> GAMING[Gaming workstation]
    BASE --> ARM[ARM build]
    BASE --> DEV[Developer image]
    DEV --> PY[Python stack]
    DEV --> NODE[Node.js stack]
</pre>

## 1. Minimal base image

Use the architecture defaults with a minimal live-user overlay.

```bash
python3 cli.py x86_64 \
  --live-profile live-minimal \
  --package-profile base \
  --service-profile common-base
```

Use this when you want a small baseline image with minimal live-user privileges.

## 2. XFCE desktop workstation

```bash
python3 cli.py x86_64 \
  --desktop xfce \
  --package-profile audio \
  --package-profile multimedia \
  --package-profile fonts-locales \
  --service-profile common-base
```

Typical output name:

```text
arch-builder-xfce-x86_64.iso
```

## 3. Office workstation

```bash
python3 cli.py x86_64 \
  --desktop workstation-office \
  --package-profile printing \
  --package-profile fonts-locales \
  --service-profile common-base \
  --service-profile common-printing
```

Good fit for LibreOffice, Thunderbird, PDF viewing, and printer support.

## 4. Gaming workstation

```bash
python3 cli.py x86_64 \
  --desktop workstation-gaming \
  --kernel linux-zen \
  --package-profile audio \
  --package-profile multimedia \
  --service-profile common-base
```

This combines the Plasma-based gaming profile with a desktop-oriented kernel choice.

## 5. Python developer image

```bash
python3 cli.py x86_64 \
  --desktop xfce \
  --package-profile dev-tools \
  --package-profile python-dev \
  --package-profile containers \
  --service-profile common-base
```

Useful for building a live development workstation with compilers, Python tooling, and containers.

## 6. Node.js developer image

```bash
python3 cli.py x86_64 \
  --desktop xfce \
  --package-profile dev-tools \
  --package-profile node-dev \
  --package-profile containers \
  --service-profile common-base
```

## 7. Security and diagnostics image

```bash
python3 cli.py x86_64 \
  --desktop wm-minimal \
  --package-profile security \
  --package-profile monitoring \
  --package-profile network-advanced \
  --service-profile common-base \
  --service-profile common-remote
```

Suited for audit, troubleshooting, and remote-access style live sessions.

## 8. ARM64 image

```bash
python3 cli.py aarch64 \
  --live-profile aarch64-live \
  --package-profile base \
  --service-profile common-base
```

Use `arm64` instead of `aarch64` when you want the alias profile naming.

## 9. Real build on a non-Arch host

```bash
sudo python3 cli.py x86_64 \
  --mode real \
  --desktop xfce \
  --force-isolated-toolchain \
  --toolchain-debug \
  --toolchain-debug-log arch-builder/toolchain-debug.log \
  --toolchain-pacman-retries 4 \
  --clean
```

Use this when host tooling is missing or when you want a more reproducible isolated build path.

## 10. Reusing previous build state

```bash
sudo python3 cli.py x86_64 \
  --mode real \
  --desktop xfce \
  --no-clean
```

Useful when iterating on a build and you intentionally want to preserve the existing tree.

---

## 11. Tutorial: Installing AUR Packages (e.g. pamac-aur, yay)

Arch-Builder supports automatically downloading, compiling, and installing packages from the AUR (Arch User Repository) during the build process using a dedicated non-root build flow with helper accounts.

### Step 1: Create or edit an AUR package profile
You can edit the default `configs/packages/aur-packages.json` file to specify the AUR package names under the `package_sources.aur` list:

```json
{
  "name": "aur-packages",
  "description": "Custom AUR packages to compile and install.",
  "package_sources": {
    "aur": [
      "yay-bin",
      "pamac-aur"
    ]
  },
  "dependencies": ["pacman"]
}
```

### Step 2: Build the ISO with the AUR profile
Run the build command and load the profile using the `-p` or `--package-profile` argument:

```bash
sudo python3 cli.py x86_64 \
  --mode real \
  --desktop xfce \
  --package-profile aur-packages
```

The orchestrator will:
1. Grant temporary passwordless sudo rights to a custom `aurbuilder` user inside the build toolchain.
2. Clone the packages, build dependencies, compile binaries, and package them as `.pkg.tar.zst`.
3. Safely install them to the live ISO target rootfs (`airootfs`) using `pacman -U`.

---

## 12. Tutorial: Installing Local Custom Packages (e.g. Calamares)

If you have pre-compiled packages (like a custom build of the `calamares` system installer or proprietary drivers), you can easily bundle them without rebuilding them each time.

### Step 1: Place packages in the local folder
Place the `.pkg.tar.zst` or `.pkg.tar.xz` package files in the dedicated local directory:
```text
configs/custom-packages/local/
```
Example path:
```text
configs/custom-packages/local/calamares-3.3.0-1-x86_64.pkg.tar.zst
```

### Step 2: Build the ISO using the custom-user profile
The `configs/packages/custom-user.json` profile is pre-configured to scan the local packages directory. Run the build with:

```bash
sudo python3 cli.py x86_64 \
  --mode real \
  --desktop xfce \
  --package-profile custom-user
```

The builder will stage all files matching `*.pkg.tar*` in the directory, verify their dependencies, and install them directly onto the live system.