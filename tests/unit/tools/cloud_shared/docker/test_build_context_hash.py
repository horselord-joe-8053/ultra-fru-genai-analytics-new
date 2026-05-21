from tools.cloud_shared.docker.build_context_hash import compute_build_context_hash


def test_compute_build_context_hash_stable(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("x")
    h1 = compute_build_context_hash(str(tmp_path), "Dockerfile")
    h2 = compute_build_context_hash(str(tmp_path), "Dockerfile")
    assert h1 == h2
    assert len(h1) == 24
