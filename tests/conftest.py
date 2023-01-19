import sys

import pytest


class TeeCapSysWrapper:
    def __init__(self, capsys):
        self.capsys = capsys

    def readouterr(self, *args, **kwargs):
        readout = self.capsys.readouterr(*args, **kwargs)
        sys.stdout.write(readout.out)
        sys.stderr.write(readout.err)
        return readout

    def disabled(self, *args, **kwargs):
        return self.capsys.disabled(*args, **kwargs)


@pytest.fixture
def tee_capsys(capsys):
    return TeeCapSysWrapper(capsys)
