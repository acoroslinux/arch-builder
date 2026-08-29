import argparse
import json
import re
import sys
from pathlib import Path

from core.orchestrator import BuildOrchestrator, BuildOrchestratorError
from core.path_utils import resolve_from_project


def _available_profiles(config_root: Path, category: str):
    category_dir = config_root / category
    if not category_dir.exists() or not category_dir.is_dir():
        return []
    return sorted([p.stem for p in category_dir.glob("*.json")])


def _slugify_name(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", (value or "").strip().lower())
    normalized = normalized.strip("-._")
    return normalized or fallback


def _parse_list_arg(arg_value):
    if not arg_value:
        return []
    items = []
    if isinstance(arg_value, list):
        for val in arg_value:
            if isinstance(val, list):
                for inner in val:
                    items.extend([x.strip() for x in inner.split(",") if x.strip()])
            elif isinstance(val, str):
                items.extend([x.strip() for x in val.split(",") if x.strip()])
    elif isinstance(arg_value, str):
        items.extend([x.strip() for x in arg_value.split(",") if x.strip()])
    return items


def _resolve_output_name(
    architecture: str, desktop: str = None, output: str = None
) -> str:
    if output:
        return output

    desktop_label = _slugify_name(desktop or "base", "base")
    arch_label = _slugify_name(architecture, "x86_64")
    return f"arch-builder-{desktop_label}-{arch_label}.iso"


def main():
    default_config_path = resolve_from_project("configs/global_build.json")
    defaults = {}
    try:
        with open(default_config_path, "r") as f:
            cfg = json.load(f)
            defaults = cfg.get("defaults", {})
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Arch-Builder: Modular and Dynamic Arch Linux ISO Builder",
        epilog="Use --help to see a detailed list of available arguments.",
    )

    # Required/Primary Arguments
    parser.add_argument(
        "--device",
        type=str,
        help="Hardware device profile (e.g., rpi4, pinebookpro)",
    )

    parser.add_argument(
        "architecture",
        nargs="?",
        default="x86_64",
        choices=["x86_64", "aarch64", "riscv64", "ppc64le", "s390x"],
        help="Target architecture (e.g., x86_64, arm64). Default: x86_64",
    )

    # Configuration and Environment
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=str(resolve_from_project("configs/global_build.json")),
        help="Path to the global configuration JSON file. Default: configs/global_build.json",
    )

    parser.add_argument(
        "--mode",
        choices=["mock", "real"],
        default="mock",
        help="Execution mode: 'mock' (simulation, no root required) or 'real' (actual build, requires root/chroot). Default: mock",
    )

    parser.add_argument(
        "--format",
        choices=["iso", "img", "raw", "qcow2", "vmdk", "vhd", "vhdx", "vdi", "tarball", "container"],
        default="iso",
        help="Build artifact format: iso, img, raw, qcow2, vmdk, vhd, vhdx, vdi, tarball, container. Default: iso",
    )

    clean_group = parser.add_mutually_exclusive_group()
    clean_group.add_argument(
        "--clean",
        dest="clean",
        action="store_true",
        help="Clean previous build artifacts before starting a new build (default).",
    )
    clean_group.add_argument(
        "--no-clean",
        dest="clean",
        action="store_false",
        help="Reuse previous build tree without pre-build cleanup.",
    )
    parser.set_defaults(clean=True)

    parser.add_argument(
        "--force-isolated-toolchain",
        action="store_true",
        help="Force isolated Arch bootstrap toolchain in real mode, even if host tools are available.",
    )

    parser.add_argument(
        "--toolchain-debug",
        action="store_true",
        help="Enable detailed toolchain diagnostics and write them to a dedicated log file.",
    )

    parser.add_argument(
        "--toolchain-debug-log",
        type=str,
        help="Optional path for toolchain diagnostics log file.",
    )

    parser.add_argument(
        "--toolchain-pacman-retries",
        type=int,
        default=3,
        help="Number of retry attempts for pacman/pacman-key operations in isolated bootstrap.",
    )

    # Customization Overrides
    parser.add_argument(
        "-k",
        "--kernel",
        type=str,
        default=defaults.get("kernel"),
        help="Kernel selection (profile in configs/system or direct package name, e.g. linux-lts).",
    )

    parser.add_argument(
        "-d",
        "--desktop",
        type=str,
        default=defaults.get("desktop"),
        help="Override the default desktop environment defined in the configuration.",
    )

    parser.add_argument(
        "-b",
        "--bootloader",
        type=str,
        default=defaults.get("bootloader"),
        help="Bootloader profile name from configs/boot.",
    )

    parser.add_argument(
        "-p",
        "--package-profile",
        "--packages",
        "--package",
        nargs="+",
        action="append",
        default=defaults.get("package_profiles", []),
        help="Package profile from configs/software. Can be provided multiple times, space or comma separated.",
    )

    parser.add_argument(
        "-s",
        "--service-profile",
        "--services",
        "--service",
        nargs="+",
        action="append",
        default=defaults.get("service_profiles", []),
        help="Common services profile from configs/services. Can be provided multiple times, space or comma separated.",
    )

    parser.add_argument(
        "--live-user",
        type=str,
        help="Override live ISO username (default from architecture config).",
    )

    parser.add_argument(
        "--live-profile",
        type=str,
        help="Live user profile name from configs/live-users.",
    )

    parser.add_argument(
        "--live-groups",
        type=str,
        help="Comma-separated group list for live user (e.g. wheel,audio,video).",
    )


    parser.add_argument(
        "--with-offline-repo",
        action="store_true",
        help="Embed an offline package repository on the ISO/Image.",
    )

    parser.add_argument(
        "--offline-repo-packages",
        type=str,
        default=None,
        help="Comma-separated list of packages to include in the offline repository.",
    )
    parser.add_argument(
        "--list-options",
        action="store_true",
        help="List available desktops, kernels, bootloaders, and package profiles.",
    )

    # Output
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output ISO file name. Default: arch-builder-<desktop>-<architecture>.iso",
    )

    # Verbosity
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging."
    )

    
    parser.add_argument(
        "--fast",
        "--quick",
        dest="fast_mode",
        action="store_true",
        help="Enable ultra-fast build mode (multi-threaded zstd level 3, fast block sizes, and optimized staging).",
    )

    parser.add_argument(
        "--tmpfs",
        action="store_true",
        help="Mount working directory as tmpfs in RAM for extreme build speed.",
    )

    args = parser.parse_args()

    # ── Handle Device Profile ───────────────────────────────────────────────────
    if getattr(args, "device", None):
        device_file = resolve_from_project(f"configs/hardware/{args.device}.json")
        if device_file.exists():
            import json
            with open(device_file) as f:
                dev_cfg = json.load(f)
            
            # Explicitly update args.architecture if not provided on CLI
            if "architecture" in dev_cfg:
                # If architecture was not passed in sys.argv (not considering flags for architecture since it is positional usually)
                arch_passed = any(a in getattr(args, "architecture", "") for a in sys.argv[1:]) if getattr(args, "architecture", None) else False
                if not arch_passed or getattr(args, "architecture", "") == "x86_64":
                    args.architecture = dev_cfg["architecture"]
            
            # Explicitly update format
            if "output_format" in dev_cfg and "--format" not in sys.argv and "-f" not in sys.argv:
                args.format = dev_cfg["output_format"]
                
            # Explicitly update bootloader
            if "bootloader" in dev_cfg and "--bootloader" not in sys.argv and "-b" not in sys.argv:
                # To prevent config_loader from crashing when we pass a dict, we can dump it to a temporary file
                # OR we just set args.bootloader = dev_cfg["bootloader"] and fix config_loader.py
                args.bootloader = dev_cfg["bootloader"]
                
    if args.architecture.lower() == "x86-64":
        args.architecture = "x86_64"
    output_name = _resolve_output_name(
        architecture=args.architecture,
        desktop=args.desktop,
        output=args.output,
    )

    config_root = resolve_from_project("configs")
    if args.list_options:
        print("Available build selections:")
        print(
            f"- architectures: {', '.join(_available_profiles(config_root, 'architectures')) or '(none)'}"
        )
        print(
            f"- desktops:      {', '.join(_available_profiles(config_root, 'desktops')) or '(none)'}"
        )
        print(
            f"- kernels:       {', '.join(_available_profiles(config_root, 'system')) or '(none)'}"
        )
        print(
            f"- bootloaders:   {', '.join(_available_profiles(config_root, 'boot')) or '(none)'}"
        )
        print(
            f"- packages:      {', '.join(_available_profiles(config_root, 'software')) or '(none)'}"
        )
        print(
            f"- services:      {', '.join(_available_profiles(config_root, 'services')) or '(none)'}"
        )
        print(
            f"- live-users:    {', '.join(_available_profiles(config_root, 'live-users')) or '(none)'}"
        )
        sys.exit(0)

    # Prepare paths
    config_path = resolve_from_project(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file '{config_path}' not found.")
        sys.exit(1)

    # Initialize Orchestrator
    parsed_live_groups = None
    if args.live_groups:
        parsed_live_groups = [
            g.strip() for g in args.live_groups.split(",") if g.strip()
        ]

    parsed_package_profiles = _parse_list_arg(args.package_profile)
    parsed_service_profiles = _parse_list_arg(args.service_profile)

    orchestrator = BuildOrchestrator(
        arch=args.architecture,
        config_path=str(config_path),
        mode=args.mode,
        clean=args.clean,
        force_isolated_toolchain=args.force_isolated_toolchain,
        toolchain_debug=args.toolchain_debug,
        toolchain_debug_log=args.toolchain_debug_log,
        toolchain_pacman_retries=args.toolchain_pacman_retries,
        desktop=args.desktop,
        kernel=args.kernel,
        bootloader=args.bootloader,
        package_profiles=parsed_package_profiles,
        service_profiles=parsed_service_profiles,
        live_profile=args.live_profile,
        live_user=args.live_user,
        live_groups=parsed_live_groups,
        fast_mode=getattr(args, "fast_mode", False),
        use_tmpfs=getattr(args, "tmpfs", False),
        with_offline_repo=getattr(args, "with_offline_repo", False),
        offline_repo_packages=_parse_list_arg(getattr(args, "offline_repo_packages", None)),)

    print("--- Arch-Builder Execution ---")
    print(f"Target Arch: {args.architecture}")
    print(f"Mode:        {args.mode}")
    print(f"Clean:       {'yes' if args.clean else 'no'}")
    if args.force_isolated_toolchain:
        print("Toolchain:   forced isolated bootstrap")
    if args.toolchain_debug:
        debug_log_target = args.toolchain_debug_log or "<workdir>/toolchain-debug.log"
        print(f"Diag Log:    {debug_log_target}")
    print(f"Config:      {config_path}")
    print(f"Output:      {output_name}")
    if args.kernel:
        print(f"Kernel:     {args.kernel} (Override)")
    if args.desktop:
        print(f"Desktop:    {args.desktop} (Override)")
    if args.bootloader:
        print(f"Bootloader: {args.bootloader} (Override)")
    if parsed_package_profiles:
        print(f"Profiles:   {', '.join(parsed_package_profiles)}")
    if parsed_service_profiles:
        print(f"Services:   {', '.join(parsed_service_profiles)}")
    if args.live_profile:
        print(f"Live Prof.: {args.live_profile}")
    if args.live_user:
        print(f"Live User:  {args.live_user} (Override)")
    if parsed_live_groups:
        print(f"Live Group: {', '.join(parsed_live_groups)}")
    print("------------------------------\n")

    try:
        result_iso = orchestrator.run_build(output_name)
        print(f"\n✅ Success! ISO created at: {result_iso}")
        if result_iso and Path(result_iso).exists():
            import hashlib
            print("🔒 Generating ISO Verification Checksums...")
            sha256_hash = hashlib.sha256()
            md5_hash = hashlib.md5()
            with open(result_iso, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(chunk)
                    md5_hash.update(chunk)
            sha256_val = sha256_hash.hexdigest()
            md5_val = md5_hash.hexdigest()

            sha256_file = Path(str(result_iso) + ".sha256")
            md5_file = Path(str(result_iso) + ".md5")
            sha256_file.write_text(f"{sha256_val}  {Path(result_iso).name}\n")
            md5_file.write_text(f"{md5_val}  {Path(result_iso).name}\n")

            print(f"   SHA256: {sha256_val} -> {sha256_file.name}")
            print(f"   MD5:    {md5_val} -> {md5_file.name}")
    except BuildOrchestratorError as e:
        print(f"\n❌ Build Orchestration Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
