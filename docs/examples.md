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