from hashlib import sha256

from pydantic import BaseModel


class SampleModel(BaseModel):
    name: str
    value: int


def test_sha256_file_streams_the_exact_file_content(tmp_path):
    from origin_com_automation.utils.hashing import sha256_file

    path = tmp_path / "large.bin"
    content = (b"origin-com-automation" * 10_000) + b"tail"
    path.write_bytes(content)

    assert sha256_file(path, chunk_size=4096) == sha256(content).hexdigest()


def test_canonical_digest_is_stable_for_models_and_mapping_order():
    from origin_com_automation.utils.hashing import canonical_digest

    model = SampleModel(name="Ion", value=2260)

    assert canonical_digest(model) == canonical_digest({"value": 2260, "name": "Ion"})


def test_controller_origin_version_uses_public_then_private_then_default():
    from origin_com_automation.utils.runtime import controller_origin_version

    assert controller_origin_version(type("Controller", (), {"origin_version": "10.1"})()) == "10.1"
    assert controller_origin_version(type("Controller", (), {"_origin_version": "10.0"})()) == "10.0"
    assert controller_origin_version(None, default="unknown") == "unknown"
