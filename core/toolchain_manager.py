import subprocess
from abc import abstractmethod
from typing import List


class ToolchainManagerError(Exception):
    """Raised when a required tool cannot be found or executed."""


class ToolchainManager:
    """
    Manage a secondary isolated chroot environment (build host) so that
    all build tools (mksquashfs, xorriso, pacman, and others) run in a
    controlled environment, avoiding conflicts with the host operating system.
    """

    def __init__(self, workdir: str, chroot_mode: bool = True):
        """
        Initialize the toolchain manager.
        :param workdir: Working directory used to simulate the build-host environment.
        :param chroot_mode: Whether to use a real chroot mount or only an in-memory/on-disk simulation.
        """
        self._workdir = workdir
        self._chroot_mode = chroot_mode

    @abstractmethod
    def setup_environment(self):
        """Prepare the simulated build-host workdir. Must be implemented by subclasses."""

    @abstractmethod
    def execute_command(self, command: List[str], chroot_path: str = None) -> str:
        """Execute a command inside the controlled environment and return stdout."""

    @abstractmethod
    def is_tool_available(self, tool_name: str) -> bool:
        """Check whether a specific tool is available in the environment."""

    # --- Mock and real implementations (tests/production) ---


class MockToolchainManager(ToolchainManager):
    """Simulate ToolchainManager behavior in mock mode for unit tests and early development without root."""

    def setup_environment(self):
        print(f"[MOCK] Simulating build-host environment setup in: {self._workdir}")
        # In a real scenario, the directory and placeholders would be created here.

    def execute_command(self, command: List[str], chroot_path: str = None) -> str:
        cmd_str = " ".join(command)
        print(
            f"[MOCK] Running simulated command in {chroot_path if chroot_path else 'main environment'}: {cmd_str}"
        )
        # Simulate successful output and an execution log entry.
        return f"Command '{command[0]}' executed successfully in mock mode.\nSimulation completed."

    def is_tool_available(self, tool_name: str) -> bool:
        print(f"[MOCK] Checking availability of tool '{tool_name}'... OK.")
        return True  # Assume tools are available during development.


class RealToolchainManager(ToolchainManager):
    """Real implementation using chroot or subprocess with elevated privileges."""

    def __init__(self, workdir: str, chroot_mode: bool = False):
        super().__init__(workdir, chroot_mode)
        # Permission checks can be added here if needed.

    def setup_environment(self):
        print(
            f"[REAL] Preparing the real build-host environment at: {self._workdir}..."
        )
        try:
            # In a real setup we would create the directory and possibly mount pseudo-filesystems.
            subprocess.run(["mkdir", "-p", self._workdir], check=True)
        except subprocess.CalledProcessError as e:
            raise ToolchainManagerError(
                f"Failed to prepare the build-host directory: {e}"
            )

    def execute_command(self, command: List[str], chroot_path: str = None) -> str:
        cmd_str = " ".join(command)
        print(
            f"[REAL] Running command in isolated environment (chroot/subprocess): {cmd_str}"
        )
        try:
            # In production we use subprocess.run with a chroot mount or sudo for isolation.
            if self._chroot_mode and chroot_path:
                full_command = ["chroot", str(chroot_path), "bash", "-c"] + command
                result = subprocess.run(full_command, capture_output=True, check=True)
                return result.stdout.decode("utf-8")
            else:
                # If not using chroot mode, run directly.
                result = subprocess.run(
                    command, capture_output=True, text=True, check=True
                )
                return result.stdout

        except subprocess.CalledProcessError as e:
            error_msg = (
                f"Error while executing command '{cmd_str}'. Stderr:\n{e.stderr}"
            )
            print(f"[ERROR] {error_msg}")
            raise ToolchainManagerError(error_msg)
        except Exception as e:
            raise ToolchainManagerError(
                f"Unexpected error while executing command: {e}"
            )

    def is_tool_available(self, tool_name: str) -> bool:
        # Check whether the binary exists in the system PATH.
        try:
            subprocess.run([tool_name, "--version"], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False


# Example usage (not intended for production):
if __name__ == "__main__":
    mock_tm = MockToolchainManager("/tmp/build-host")
    mock_tm.setup_environment()
    output = mock_tm.execute_command(["ls", "/etc"])
    print("\n--- Test Output ---")
    print(output)
