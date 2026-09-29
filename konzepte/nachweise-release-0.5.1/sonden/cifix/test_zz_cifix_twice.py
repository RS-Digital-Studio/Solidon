import os
import sys


def test_zweimal():
    before = os.environ["APPDATA"]
    import tests.conftest  # noqa: F401

    print("\nconftest", sys.modules["conftest"] is sys.modules["tests.conftest"], before, os.environ["APPDATA"])
