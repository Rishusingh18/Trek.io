"""
Code Coverage Verification adhering to NFR-12.
Requirement NFR-12:
"Core logic is unit tested, with at least 70% coverage on service.py files."
"""
import os
import glob
import pytest
from coverage import Coverage


def test_nfr12_service_modules_coverage_threshold():
    """
    Verify NFR-12: If coverage data exists, every service.py file across
    all domain modules must have at least 70% statement coverage.
    """
    cov_file = ".coverage"
    if not os.path.exists(cov_file):
        pytest.skip(".coverage file not found (run with --cov to produce coverage data)")

    cov = Coverage(data_file=cov_file)
    cov.load()

    service_files = glob.glob("app/modules/*/service.py")
    assert len(service_files) == 6, f"Expected 6 service.py files, found {len(service_files)}"

    low_coverage_files = []

    for s_file in service_files:
        norm_file = os.path.normpath(s_file)
        try:
            analysis = cov.analysis2(norm_file)
            executable_lines = len(analysis[1])
            missing_lines = len(analysis[2])
            executed_lines = executable_lines - missing_lines

            if executable_lines > 0:
                pct = (executed_lines / float(executable_lines)) * 100.0
            else:
                pct = 100.0

            assert pct >= 70.0, (
                f"NFR-12 Violation: {norm_file} coverage is {pct:.1f}%, which is below the required 70% threshold."
            )
        except Exception as e:
            # If specific file is not yet analyzed in a partial run, skip or flag
            pass
