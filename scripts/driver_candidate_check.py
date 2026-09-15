"""Offline tests for constrained GameWorld cua-driver patches."""

import unittest

from fps_bench.driver_candidate import validate_patch


PREFIXES = ["cua-driver/rust/crates/platform-linux/src/"]


def patch(path="cua-driver/rust/crates/platform-linux/src/input/mod.rs"):
    return f"""diff --git a/{path} b/{path}
index 1111111..2222222 100644
--- a/{path}
+++ b/{path}
@@ -1 +1 @@
-old
+new
""".encode()


class PatchTests(unittest.TestCase):
    def test_accepts_allowlisted_existing_text_patch(self):
        result = validate_patch(patch(), PREFIXES)
        self.assertEqual(result["paths"], ["cua-driver/rust/crates/platform-linux/src/input/mod.rs"])
        self.assertEqual(result["bytes"], len(patch()))

    def test_rejects_out_of_scope_and_traversal(self):
        for path in ("fps_bench/agent.py", "cua-driver/rust/crates/platform-linux/src/../Cargo.toml"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_patch(patch(path), PREFIXES)

    def test_accepts_utf8_body_without_relaxing_paths(self):
        body = patch().replace(b"-old", "-old \u2014 comment".encode("utf-8"))
        self.assertEqual(validate_patch(body, PREFIXES)["bytes"], len(body))
        with self.assertRaises(ValueError):
            validate_patch(patch("cua-driver/rust/crates/platform-linux/src/\u00e9.rs"), PREFIXES)
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            validate_patch(patch().replace(b"-old", b"-\xff"), PREFIXES)

    def test_unicode_line_separator_in_body_is_not_a_diff_header(self):
        body = patch().replace(b"-old", "-old\u2028diff --git not a header".encode("utf-8"))
        self.assertEqual(len(validate_patch(body, PREFIXES)["paths"]), 1)

    def test_rejects_new_deleted_binary_and_renamed_files(self):
        for marker in ("new file mode 100644", "deleted file mode 100644", "GIT binary patch",
                       "rename from old"):
            value = patch().replace(b"index 1111111..2222222 100644", marker.encode())
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                validate_patch(value, PREFIXES)

    def test_rejects_header_mismatch_and_incomplete_diff(self):
        with self.assertRaises(ValueError):
            validate_patch(patch().replace(b"+++ b/", b"+++ b/other/"), PREFIXES)
        with self.assertRaises(ValueError):
            validate_patch(patch().replace(b"@@ -1 +1 @@\n", b""), PREFIXES)

    def test_rejects_duplicate_files_and_non_diff_preamble(self):
        with self.assertRaises(ValueError):
            validate_patch(patch() + patch(), PREFIXES)
        with self.assertRaises(ValueError):
            validate_patch(b"rationale\n" + patch(), PREFIXES)


if __name__ == "__main__":
    unittest.main()
