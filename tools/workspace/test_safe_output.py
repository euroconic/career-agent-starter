import hashlib
import tempfile
import unittest
from pathlib import Path

from safe_output import PublishConflict, publish_bytes


def digest(data):
    return hashlib.sha256(data).hexdigest()


class SafeOutputTests(unittest.TestCase):
    def test_new_destination_is_published_after_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "final.bin"
            observed = []

            def validate(staged):
                observed.append(staged.parent)
                self.assertEqual(staged.read_bytes(), b"new bytes")

            publish_bytes(target, b"new bytes", validator=validate, must_be_absent=True)
            self.assertEqual(target.read_bytes(), b"new bytes")
            self.assertEqual(observed, [target.parent])

    def test_expected_hash_allows_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "final.bin"
            target.write_bytes(b"old")
            publish_bytes(target, b"new", validator=lambda _: None, expected_sha256=digest(b"old"))
            self.assertEqual(target.read_bytes(), b"new")

    def test_validation_failure_preserves_existing_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "final.bin"
            target.write_bytes(b"old")

            def reject(_):
                raise ValueError("invalid staged output")

            with self.assertRaisesRegex(ValueError, "invalid staged output"):
                publish_bytes(target, b"bad", validator=reject, expected_sha256=digest(b"old"))
            self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual(list(Path(directory).glob("*.stage")), [])

    def test_changed_destination_during_validation_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "final.bin"
            target.write_bytes(b"old")

            def concurrent_update(_):
                target.write_bytes(b"concurrent")

            with self.assertRaises(PublishConflict):
                publish_bytes(target, b"ours", validator=concurrent_update, expected_sha256=digest(b"old"))
            self.assertEqual(target.read_bytes(), b"concurrent")

    def test_created_destination_during_validation_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "final.bin"

            def concurrent_create(_):
                target.write_bytes(b"other writer")

            with self.assertRaises(PublishConflict):
                publish_bytes(target, b"ours", validator=concurrent_create, must_be_absent=True)
            self.assertEqual(target.read_bytes(), b"other writer")

    def test_requires_exactly_one_precondition(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "final.bin"
            with self.assertRaises(ValueError):
                publish_bytes(target, b"x", validator=lambda _: None)
            with self.assertRaises(ValueError):
                publish_bytes(target, b"x", validator=lambda _: None, expected_sha256=digest(b"x"), must_be_absent=True)

    def test_symlink_destination_rejected_without_changing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / "real.bin"
            real.write_bytes(b"old")
            target = Path(directory) / "current.bin"
            target.symlink_to(real)
            with self.assertRaisesRegex(PublishConflict, "symbolic link"):
                publish_bytes(target, b"new", validator=lambda _: None, expected_sha256=digest(b"old"))
            self.assertTrue(target.is_symlink())
            self.assertEqual(real.read_bytes(), b"old")

    def test_dangling_symlink_is_not_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "current.bin"
            target.symlink_to(Path(directory) / "missing.bin")
            with self.assertRaisesRegex(PublishConflict, "symbolic link"):
                publish_bytes(target, b"new", validator=lambda _: None, must_be_absent=True)
            self.assertTrue(target.is_symlink())

    def test_symlink_created_during_validation_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            real = Path(directory) / "real.bin"
            real.write_bytes(b"old")
            target = Path(directory) / "current.bin"
            target.write_bytes(b"old")

            def replace_with_link(_):
                target.unlink()
                target.symlink_to(real)

            with self.assertRaisesRegex(PublishConflict, "symbolic link"):
                publish_bytes(target, b"new", validator=replace_with_link, expected_sha256=digest(b"old"))
            self.assertTrue(target.is_symlink())
            self.assertEqual(real.read_bytes(), b"old")
            self.assertEqual(list(Path(directory).glob("*.stage")), [])


if __name__ == "__main__":
    unittest.main()
