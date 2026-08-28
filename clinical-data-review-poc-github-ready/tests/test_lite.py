#!/usr/bin/env python
"""
Lightweight test runner - checks syntax and basic imports without full Spark execution.
Run with: python tests/test_lite.py
"""
import os
import sys

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC_DIR)
os.environ["PYTHONPATH"] = SRC_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")

print("=" * 60)
print("LIGHT SMOKE TEST - Checking core modules")
print("=" * 60)

def test_imports():
    """Test that all core modules can be imported."""
    print("\n[1/5] Testing imports...")
    try:
        import config
        print("  OK: config")
        
        import ingest
        print("  OK: ingest")
        
        import quality_checks
        print("  OK: quality_checks")
        
        import query_drafting
        print("  OK: query_drafting")
        
        import report
        print("  OK: report")
        
        return True
    except ImportError as e:
        print(f"  FAILED: {e}")
        return False

def test_config():
    """Test configuration values."""
    print("\n[2/5] Testing configuration...")
    try:
        import config
        assert hasattr(config, 'REVIEW_DATE'), "Missing REVIEW_DATE"
        assert hasattr(config, 'STALE_DATA_DAYS'), "Missing STALE_DATA_DAYS"
        assert hasattr(config, 'HIGH_SEVERITY_THRESHOLD'), "Missing HIGH_SEVERITY_THRESHOLD"
        print(f"  OK: REVIEW_DATE = {config.REVIEW_DATE}")
        print(f"  OK: STALE_DATA_DAYS = {config.STALE_DATA_DAYS}")
        print(f"  OK: HIGH_SEVERITY_THRESHOLD = {config.HIGH_SEVERITY_THRESHOLD}")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def test_pyspark():
    """Test that PySpark can be imported."""
    print("\n[3/5] Testing PySpark availability...")
    try:
        import pyspark
        from pyspark.sql import SparkSession
        print(f"  OK: PySpark {pyspark.__version__}")
        return True
    except ImportError as e:
        print(f"  FAILED: {e}")
        return False

def test_sql_file():
    """Test that SQL quality checks file exists."""
    print("\n[4/5] Testing SQL file...")
    try:
        sql_path = os.path.join(os.path.dirname(SRC_DIR), "sql", "quality_checks.sql")
        assert os.path.exists(sql_path), f"SQL file not found: {sql_path}"
        with open(sql_path, 'r') as f:
            content = f.read()
            assert len(content) > 0, "SQL file is empty"
        print(f"  OK: Found {len(content)} bytes in quality_checks.sql")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def test_data_file():
    """Test that sample data file exists."""
    print("\n[5/5] Testing data file...")
    try:
        data_path = os.path.join(os.path.dirname(SRC_DIR), "data", "clinical_records.csv")
        assert os.path.exists(data_path), f"Data file not found: {data_path}"
        with open(data_path, 'r') as f:
            lines = f.readlines()
        print(f"  OK: Found {len(lines)} lines in clinical_records.csv")
        return True
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

def main():
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Configuration", test_config()))
    results.append(("PySpark", test_pyspark()))
    results.append(("SQL File", test_sql_file()))
    results.append(("Data File", test_data_file()))
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:20s} {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n[OK] All smoke tests passed!")
        print("\nTo run the full test suite with Spark:")
        print("  python tests/test_quality_checks.py")
        return 0
    else:
        print("\n[FAIL] Some tests failed. Fix the issues above and try again.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
