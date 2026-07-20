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
        "architecture",
        nargs="?",
        default="x86_64",
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
        help="Kernel selection (profile in configs/kernels or direct package name, e.g. linux-lts).",
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
        help="Bootloader profile name from configs/bootloaders.",
    )

    parser.add_argument(
        "-p",
        "--package-profile",
        action="append",
        default=defaults.get("package_profiles", []),
        help="Package profile from configs/packages. Can be provided multiple times.",
    )

    parser.add_argument(
        "-s",
        "--service-profile",
        action="append",
        default=defaults.get("service_profiles", []),
        help="Common services profile from configs/services. Can be provided multiple times.",
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

    args = parser.parse_args()
    if args.architecture.lower() not in ("x86_64", "x86-64"):
        print(
            f"Error: Architecture '{args.architecture}' is not supported. Only x86_64 is supported."
        )
        sys.exit(1)
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
            f"- kernels:       {', '.join(_available_profiles(config_root, 'kernels')) or '(none)'}"
        )
        print(
            f"- bootloaders:   {', '.join(_available_profiles(config_root, 'bootloaders')) or '(none)'}"
        )
        print(
            f"- packages:      {', '.join(_available_profiles(config_root, 'packages')) or '(none)'}"
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
        package_profiles=args.package_profile,
        service_profiles=args.service_profile,
        live_profile=args.live_profile,
        live_user=args.live_user,
        live_groups=parsed_live_groups,
    )

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
    if args.package_profile:
        print(f"Profiles:   {', '.join(args.package_profile)}")
    if args.service_profile:
        print(f"Services:   {', '.join(args.service_profile)}")
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
    except BuildOrchestratorError as e:
        print(f"\n❌ Build Orchestration Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
