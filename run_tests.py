#!/usr/bin/env python3
import subprocess
import sys

# This wrapper ensures the test command runs directly through the shell
# and avoids complex import issues from programmatic unittest execution.
print("=============================")
print("STARTING UNIT TEST EXECUTION...")
print("=============================\n")

# Run the complete test suite. Keeping this wrapper complete is important:
# CI/local checks should not pass while integration or subsystem tests fail.
try:
    result = subprocess.run(
        ["python3", "-m", "unittest", "discover", "-s", "tests"],
        check=True, 
        capture_output=True, 
        text=True
    )
    print("\n--- Unit Test Output ---")
    print(result.stdout)
    print(result.stderr)

except subprocess.CalledProcessError as e:
    print("\n❌ TEST FAILURE (non-zero exit code): tests failed.")
    print("------------------------------------")
    print("STDOUT:", e.stdout)
    print("STDERR:", e.stderr)
    sys.exit(e.returncode)
except FileNotFoundError:
    print("\n🚨 FATAL ERROR: the 'python3' command was not found or the 'unittest' module is missing.")
    sys.exit(127)

finally:
    # Keep the wrapper explicit even though no cleanup is currently needed.
    pass
