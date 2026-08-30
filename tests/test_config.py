import platform
import pytest
from unittest import mock

def test_detect_system_linux():
    with mock.patch.object(platform, 'system', return_value='Linux'):
        from danger_guard.config import detect_system
        assert detect_system() == 'Linux'

def test_detect_system_darwin():
    with mock.patch.object(platform, 'system', return_value='Darwin'):
        from danger_guard.config import detect_system
        assert detect_system() == 'Darwin'

def test_detect_system_windows():
    with mock.patch.object(platform, 'system', return_value='Windows'):
        from danger_guard.config import detect_system
        assert detect_system() == 'Windows'

@pytest.mark.parametrize('cygwin_like', ['CYGWIN_NT-10.0', 'MINGW64_NT-10.0', 'MSYS_NT-10.0'])
def test_detect_system_cygwin_family_maps_to_windows(cygwin_like):
    with mock.patch.object(platform, 'system', return_value=cygwin_like):
        from danger_guard.config import detect_system
        assert detect_system() == 'Windows'

def test_detect_system_unknown_falls_back_to_linux():
    with mock.patch.object(platform, 'system', return_value='FreeBSD'):
        from danger_guard.config import detect_system
        assert detect_system() == 'Linux'
