import os

from app.core.report import QT_PLATFORM_BEFORE_VARIABLE


def test_verschmutzt():
    os.environ[QT_PLATFORM_BEFORE_VARIABLE] = "wayland"
