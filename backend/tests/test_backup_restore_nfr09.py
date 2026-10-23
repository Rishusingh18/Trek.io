"""
Tests for Daily Backup & Restore Drills adhering to NFR-09.
Requirement NFR-09:
"Data shall be backed up daily and restorable (Reliability / Restore drill)."
"""
import os
import time
import tempfile
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from scripts.backup import run_backup
from scripts.restore import run_restore


def test_nfr09_backup_script_execution_and_retention():
    """
    NFR-09: Verifies that the backup script executes pg_dump with custom compressed format,
    creates the target backup file, and prunes files exceeding the retention window.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Create a simulated older backup outside the 7-day retention window
        old_backup = tmp_path / "backup_testdb_20260101_000000.dump"
        old_backup.write_bytes(b"dummy backup data")
        # Set file modification time to 15 days ago
        fifteen_days_ago = time.time() - (15 * 86400)
        os.utime(old_backup, (fifteen_days_ago, fifteen_days_ago))

        # 2. Mock subprocess.run to simulate successful pg_dump execution
        def mock_subprocess_run(cmd, env=None, capture_output=True, text=True):
            # Assert proper pg_dump flags
            assert cmd[0] == "pg_dump"
            assert "-Fc" in cmd  # Custom format
            assert "-Z" in cmd and "9" in cmd  # Max compression
            # Write a valid dummy file where -f specifies
            f_idx = cmd.index("-f")
            out_file = Path(cmd[f_idx + 1])
            out_file.write_bytes(b"PGDMP_TEST_MOCK_DATA")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            new_backup = run_backup(
                output_dir=str(tmp_path),
                retention_days=7,
                db_url="postgresql://postgres:postgres@localhost:5432/testdb"
            )

        # 3. Verify new backup exists
        assert new_backup.exists()
        assert new_backup.name.startswith("backup_testdb_")
        assert new_backup.name.endswith(".dump")
        assert new_backup.read_bytes() == b"PGDMP_TEST_MOCK_DATA"

        # 4. Verify old backup exceeding retention was pruned
        assert not old_backup.exists(), "Old backup exceeding retention should have been deleted"


def test_nfr09_restore_script_execution_with_clean_flags():
    """
    NFR-09: Verifies that the restore script validates the dump file existence and
    invokes pg_restore with safe drop-and-replace flags (--clean --if-exists).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        backup_file = Path(tmp_dir) / "backup_testdb_20261023_120000.dump"
        backup_file.write_bytes(b"DUMP_PAYLOAD_TEST")

        captured_commands = []

        def mock_subprocess_run(cmd, env=None, capture_output=True, text=True, timeout=None):
            captured_commands.append(cmd)
            return MagicMock(returncode=0, stdout="Restored successfully", stderr="")

        with patch("subprocess.run", side_effect=mock_subprocess_run):
            run_restore(
                backup_file=str(backup_file),
                db_url="postgresql://test_user:test_pass@localhost:5432/testdb"
            )

        # Verify pg_restore command structure
        restore_cmds = [c for c in captured_commands if c[0] == "pg_restore"]
        assert len(restore_cmds) == 1
        restore_cmd = restore_cmds[0]

        assert "-d" in restore_cmd and "testdb" in restore_cmd
        assert "-U" in restore_cmd and "test_user" in restore_cmd
        assert "--clean" in restore_cmd
        assert "--if-exists" in restore_cmd
        assert "--no-owner" in restore_cmd
        assert str(backup_file) in restore_cmd


def test_nfr09_restore_script_missing_file_raises_error():
    """
    NFR-09: Restoring a non-existent backup file raises FileNotFoundError.
    """
    with pytest.raises(FileNotFoundError):
        run_restore(backup_file="non_existent_archive_12345.dump")
