# Custom Packages

Place user-provided package files in `configs/custom-packages/local/`.

Supported local package artifacts:
- `*.pkg.tar.zst`
- `*.pkg.tar.xz`

These files can be installed during the build using the `package_sources.local_dir` setting in a package profile.

## AUR support

You can also define AUR packages using `package_sources.aur`.
During real builds, the chroot installer will:
1. install `git` and `base-devel`
2. create a non-root `aurbuilder` user
3. clone and build each AUR package with `makepkg -si`

## Example profile

See `configs/packages/custom-user.json`.
