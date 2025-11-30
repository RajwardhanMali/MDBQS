from app.services.fusion import fuse


def test_fuse_placeholder():
    assert fuse([]) == "fused result"
