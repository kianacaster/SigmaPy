import pytest
from emulator import EmulatorState
import common
import arrbuf as ab

def test_emulator_init():
    es = EmulatorState(common.ES_gui_thread, ab)
    assert es is not None
    assert hasattr(es, 'ab')
    assert es.vec16 is not None
    assert es.vec32 is not None
    assert es.vec64 is not None
