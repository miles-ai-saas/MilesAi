import time

from app.utils.idgen import generate_id, generate_uuid, is_uuid7, uuid7_version


def test_generate_uuid_is_version_7() -> None:
    value = generate_uuid()
    assert uuid7_version(value) == 7
    assert (value.int >> 62) & 0x3 == 0b10
    assert is_uuid7(value)
    assert len(generate_id()) == 32


def test_generate_uuid_time_ordered() -> None:
    first = generate_uuid()
    time.sleep(0.002)
    second = generate_uuid()
    assert first.int < second.int
