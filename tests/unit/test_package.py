import know_your_project


def test_package_version() -> None:
    assert know_your_project.__version__ == "0.1.0"
