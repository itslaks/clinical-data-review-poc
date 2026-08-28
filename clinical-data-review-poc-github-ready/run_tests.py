#!/usr/bin/env python
"""
Test runner - run from project root with: python run_tests.py
This script runs all available tests.
"""
import subprocess
import sys
import os
import shutil


def validate_python_for_pyspark():
    """Fail early with clear guidance when PySpark is incompatible with the active interpreter."""
    major, minor = sys.version_info[:2]
    if major != 3 or minor >= 13:
        print("ERROR: This project is not compatible with Python 3.13+ on Windows.")
        print("PySpark on Windows commonly fails during startup with 'The system cannot find the path specified'.")
        print("Use Python 3.11 or 3.12 instead.")
        print()
        print("Recommended setup:")
        print("  py -3.12 -m venv .venv")
        print("  .\\.venv\\Scripts\\python.exe -m pip install -U pip")
        print("  .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt")
        print("  .\\.venv\\Scripts\\python.exe run_tests.py")
        return False
    return True


def ensure_java_home():
    """Set JAVA_HOME to the installed JDK if the environment is stale or missing."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home and os.path.exists(os.path.join(java_home, "bin", "java.exe")):
        os.environ["PATH"] = os.path.join(java_home, "bin") + os.pathsep + os.environ.get("PATH", "")
        return

    candidates = [
        r"C:\Program Files\OpenLogic\jdk-11.0.19.7-hotspot",
        r"C:\Program Files\Java\jdk-11.0.19",
        r"C:\Program Files\OpenJDK",
        r"C:\Program Files\Eclipse Adoptium",
    ]
    for base in candidates:
        if os.path.isdir(base):
            for root, dirs, _ in os.walk(base):
                java_exe = os.path.join(root, "bin", "java.exe")
                if os.path.exists(java_exe):
                    os.environ["JAVA_HOME"] = root
                    os.environ["PATH"] = os.path.join(root, "bin") + os.pathsep + os.environ.get("PATH", "")
                    return
    if shutil.which("java"):
        java_path = shutil.which("java")
        java_root = os.path.dirname(os.path.dirname(java_path))
        os.environ["JAVA_HOME"] = java_root
        os.environ["PATH"] = os.path.join(java_root, "bin") + os.pathsep + os.environ.get("PATH", "")


def run_test(test_script, description):
    """Run a single test script and report results."""
    print(f"\n{'='*70}")
    print(f"Running: {description}")
    print(f"Script:  {test_script}")
    print('='*70)
    
    try:
        result = subprocess.run(
            [sys.executable, test_script],
            timeout=300,
            text=True
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"ERROR: Test timed out after 300 seconds")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False


def main():
    if not validate_python_for_pyspark():
        return 2

    ensure_java_home()

    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)
    
    print("="*70)
    print("CLINICAL DATA REVIEW TEST SUITE")
    print("="*70)
    print(f"Working directory: {project_root}\n")
    
    tests = [
        ('tests/test_lite.py', 'Smoke tests (fast, no Spark)'),
        ('tests/test_quality_checks.py', 'Full test suite (requires Spark)'),
    ]
    
    results = []
    for test_script, description in tests:
        test_path = os.path.join(project_root, test_script)
        if os.path.exists(test_path):
            passed = run_test(test_script, description)
            results.append((description, passed))
        else:
            print(f"\nWARNING: Test file not found: {test_script}")
            results.append((description, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for description, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status:8s} {description}")
    
    all_passed = all(r[1] for r in results)
    
    print("="*70)
    if all_passed:
        print("SUCCESS: All tests passed!")
        return 0
    else:
        print("FAILURE: Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
