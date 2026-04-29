def test_server_package_imports():
    import server

    assert server.__version__ == "0.1.0"


def test_client_package_imports():
    import client

    assert client.__version__ == "0.1.0"
