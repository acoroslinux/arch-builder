#!/bin/bash
# Script to compile Calamares from AUR and place it in the local packages repository

set -e

# Define directories
PROJECT_DIR="/repos/frs/projects/pep-void/arch-builder"
LOCAL_PKG_DIR="${PROJECT_DIR}/configs/custom-packages/local"
BUILD_DIR="/tmp/calamares-build"

echo "=== Calamares Compilation Script ==="

# 1. Ensure we are running on Arch Linux
if [ ! -f /etc/arch-release ]; then
    echo "Error: This script must be run on Arch Linux."
    exit 1
fi

# 2. Ensure local package directory exists
mkdir -p "${LOCAL_PKG_DIR}"

# 2b. Install build prerequisites (base-devel and git)
echo "Installing build prerequisites (base-devel, git)..."
if [ "$EUID" -eq 0 ]; then
    pacman -Sy --needed --noconfirm base-devel git
else
    sudo pacman -Sy --needed --noconfirm base-devel git
fi

# 3. Clean and prepare build directory
echo "Preparing build directory at ${BUILD_DIR}..."
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

# 4. Clone AUR package repository
echo "Cloning Calamares AUR package repository..."
git clone https://aur.archlinux.org/calamares.git

# 5. Build Calamares using makepkg
cd calamares
echo "Compiling Calamares with makepkg (this may take a few minutes)..."
# Note: makepkg cannot be run as root. If running as root, we should use a non-root user.
if [ "$EUID" -eq 0 ]; then
    # We are root. Find a non-root user or create one
    BUILD_USER=$(logname 2>/dev/null || echo ${SUDO_USER:-nobody})
    if [ "${BUILD_USER}" = "root" ] || [ "${BUILD_USER}" = "nobody" ] || ! id -u "${BUILD_USER}" >/dev/null 2>&1; then
        # Create a temporary user if no real user is available
        id -u cala-builder >/dev/null 2>&1 || useradd -m cala-builder
        BUILD_USER="cala-builder"
    fi
    echo "Running build as user: ${BUILD_USER}"
    
    # Ensure BUILD_USER has passwordless sudo inside the chroot for installing dependencies
    mkdir -p /etc/sudoers.d
    echo "${BUILD_USER} ALL=(ALL:ALL) NOPASSWD: ALL" > "/etc/sudoers.d/99-${BUILD_USER}"
    chmod 0440 "/etc/sudoers.d/99-${BUILD_USER}"
    
    chown -R "${BUILD_USER}:${BUILD_USER}" "${BUILD_DIR}"
    
    # Run makepkg as the selected user
    runuser -u "${BUILD_USER}" -- makepkg -s --noconfirm
else
    # We are already a non-root user
    makepkg -s --noconfirm
fi

# 6. Copy the compiled package to the local repo
echo "Locating compiled package..."
PKG_FILES=( *.pkg.tar.zst )

if [ ${#PKG_FILES[@]} -eq 0 ] || [ ! -f "${PKG_FILES[0]}" ]; then
    echo "Error: No compiled package file found!"
    exit 1
fi

echo "Copying compiled package ${PKG_FILES[0]} to local repo..."
cp "${PKG_FILES[0]}" "${LOCAL_PKG_DIR}/"

# 7. Clean up
echo "Cleaning up build files..."
rm -rf "${BUILD_DIR}"

echo "=== Build Succeeded! ==="
echo "Package is now located at: ${LOCAL_PKG_DIR}/${PKG_FILES[0]}"
