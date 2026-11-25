"""The one-window rule (CD-09): later launches hand their paths over."""

from __future__ import annotations

from mishkah.services.single_instance import (
    InstanceServer,
    paths_to_payload,
    payload_to_paths,
    send_to_running_instance,
    server_name,
    start_server,
)


def test_the_payload_round_trips():
    paths = ["/tmp/a.txt", "/tmp/مِلَفّ.md"]
    assert payload_to_paths(paths_to_payload(paths)) == paths
    assert payload_to_paths(b"\n") == []
    assert paths_to_payload([]) == b""


def test_the_socket_name_is_per_user():
    name = server_name()
    assert name.startswith("mishkah-note-")
    assert server_name("x").endswith("-x")


def test_a_second_launch_is_handed_to_the_first(qapp):
    from PySide6.QtTest import QTest

    name = server_name("test-owner")
    server = start_server(name=name)
    assert server is not None
    received = []
    server.paths_received.connect(lambda paths: received.extend(paths))
    try:
        assert send_to_running_instance(["/tmp/one.txt"], name=name) is True
        deadline = 0
        while not received and deadline < 40:
            QTest.qWait(25)
            deadline += 1
        assert received == ["/tmp/one.txt"]
    finally:
        server.close()


def test_no_running_instance_means_a_normal_start(qapp):
    name = server_name("nobody-here")
    InstanceServer(name=name).close()          # make sure nothing listens
    assert send_to_running_instance(["/tmp/x.txt"], name=name) is False
