with open('/iso-builder/arch-builder/core/chroot_manager.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('                install_cmd = ('):
        lines[i] = '                    install_cmd = (\n'
    if line.startswith('                    "set -e; "'):
        # this one seems to need to be fixed
        pass

with open('/iso-builder/arch-builder/core/chroot_manager.py', 'w') as f:
    f.writelines(lines)
