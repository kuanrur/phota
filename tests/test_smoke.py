import phota


def test_version_exposed():
    assert isinstance(phota.__version__, str)
    assert phota.__version__
