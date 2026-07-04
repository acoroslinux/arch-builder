#!/usr/bin/env python3
import subprocess
import sys

# This wrapper ensures the test command runs directly through the shell
# and avoids complex import issues from programmatic unittest execution.
print("=============================")
print("STARTING UNIT TEST EXECUTION...")
print("=============================\n")

# Run 'python3 -m unittest tests.test_config_loader' directly in the shell.
try:
    result = subprocess.run(
        ['python3', '-m', 'unittest', 'tests.test_config_loader'], 
        check=True, 
        capture_output=True, 
        text=True
    )
    print("\n--- Unit Test Output ---")
    print(result.stdout)

except subprocess.CalledProcessError as e:
    print("\n❌ TEST FAILURE (non-zero exit code): tests failed.")
    print("------------------------------------")
    print("STDOUT:", e.stdout)
    print("STDERR:", e.stderr)
except FileNotFoundError:
    print("\n🚨 FATAL ERROR: the 'python3' command was not found or the 'unittest' module is missing.")

finally:
    # Keep the wrapper explicit even though no cleanup is currently needed.
    pass