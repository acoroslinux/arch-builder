#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to python path to import core modules
sys.path.insert(0, '/repos/frs/projects/pep-void/arch-builder')

from core.toolchain import ToolchainManager
from core.path_utils import resolve_from_project

def main():
    print("=== Isolated Calamares Build ===")
    
    # We want to use the workdir as configured or standard
    workdir_base = resolve_from_project("arch-builder/workdir/x86_64")
    
    # Initialize the ToolchainManager in real mode, forcing isolated bootstrap
    toolchain = ToolchainManager(
        workdir_base=workdir_base,
        mode="real",
        force_isolated=True,
    )
    
    try:
        # Step 1: Initialize/mount the isolated build host
        print("Setting up isolated build host chroot...")
        toolchain.setup()
        
        # Step 2: Run build_calamares.sh inside the build host
        # The project directory is mounted inside the chroot under /repos/frs/projects/pep-void/arch-builder
        print("Executing build_calamares.sh inside the isolated chroot...")
        build_script = "/repos/frs/projects/pep-void/arch-builder/scripts/build_calamares.sh"
        
        # Run it inside the chroot
        toolchain.run_tool([build_script])
        
        print("\n✅ Build completed successfully inside the isolated environment!")
        
    except Exception as e:
        print(f"\n❌ Isolated Build Failed: {e}")
        sys.exit(1)
        
    finally:
        # Step 3: Always clean up mounts!
        print("Cleaning up isolated build host mounts...")
        toolchain.cleanup()

if __name__ == "__main__":
    main()
