from src.message import Message


class TestMessageRoundTrip:
    def test_basic(self):
        msg = Message("user", "Hello")
        data = msg.to_dict()
        restored = Message.from_dict(data)
        assert restored.role == "user"
        assert restored.content == "Hello"
        assert restored.image is None
        assert restored.metadata == {}

    def test_with_image(self):
        msg = Message("user", "Look", image="img.png")
        restored = Message.from_dict(msg.to_dict())
        assert restored.image == "img.png"

    def test_with_metadata(self):
        msg = Message("assistant", "Hi", metadata={"cost": 0.01})
        restored = Message.from_dict(msg.to_dict())
        assert restored.metadata == {"cost": 0.01}

    def test_none_content(self):
        msg = Message("user", None, image="img.png")
        data = msg.to_dict()
        assert "content" not in data
        restored = Message.from_dict(data)
        assert restored.content is None


class TestToDict:
    def test_omits_none_fields(self):
        data = Message("user", "Hi").to_dict()
        assert "image" not in data
        assert "metadata" not in data

    def test_includes_all_fields(self):
        data = Message("user", "Hi", "img.png", {"k": "v"}).to_dict()
        assert set(data.keys()) == {"role", "content", "image", "metadata"}
