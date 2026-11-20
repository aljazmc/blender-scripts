"""Tests for scripts/common.py, which needs no bpy until a project is built.
Run: python3 -m unittest discover tests"""
import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
common = importlib.import_module("common")


class LoadProjectTest(unittest.TestCase):

    def test_exits_with_a_message_on_a_bad_project(self):
        cases = {
            "no arguments": (["blender", "-b", "-P", "exportpng.py"],
                             "usage: blender -b -P <script> -- <project>"),
            "no project": (["blender", "-b", "-P", "exportpng.py", "--"],
                           "usage: blender -b -P <script> -- <project>"),
            "unknown project": (["blender", "--", "no-such-project"],
                                "project not found: "),
        }
        for case, (argv, message) in cases.items():
            with self.subTest(case), mock.patch.object(sys, "argv", argv):
                with self.assertRaises(SystemExit) as raised:
                    common.load_project("build")
                self.assertIn(message, str(raised.exception.code))


if __name__ == "__main__":
    unittest.main()
