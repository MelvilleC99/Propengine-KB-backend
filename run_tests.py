#!/usr/bin/env python3
"""Run all backend tests with detailed output"""

import subprocess
import sys

def run_tests():
    """Run pytest with appropriate configuration"""
    print("=" * 60)
    print("PropEngine Backend - Test Suite")
    print("=" * 60)
    
    # Run pytest with verbose output and color
    result = subprocess.run([
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--color=yes",
        "--tb=short"
    ])
    
    return result.returncode

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
