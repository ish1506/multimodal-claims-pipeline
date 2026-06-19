from pathlib import Path

from claim_review.context import build_claim_context
from claim_review.images import ensure_openai_supported_image, prepare_images


def test_prepare_images_detects_jpeg_from_bytes(tmp_path: Path):
    image_path = tmp_path / "dataset" / "images" / "test" / "case_001" / "img_1.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")
    row = {
        "user_id": "u1",
        "image_paths": "images/test/case_001/img_1.jpg",
        "user_claim": "door dent",
        "claim_object": "car",
    }
    context = build_claim_context(row, 0, {}, [])
    prepared = prepare_images(tmp_path, context)
    assert prepared[0].image_id == "img_1"
    assert prepared[0].mime_type == "image/jpeg"
    assert prepared[0].data_url.startswith("data:image/jpeg;base64,")


def test_unsupported_decodable_images_are_transcoded_to_jpeg(tmp_path: Path):
    from PIL import Image

    source = tmp_path / "hidden_avif.jpg"
    Image.new("RGB", (2, 2), color=(200, 10, 20)).save(source, format="PNG")
    data = source.read_bytes()

    transport_data, transport_mime_type = ensure_openai_supported_image(data, "image/avif", source)

    assert transport_mime_type == "image/jpeg"
    assert transport_data.startswith(b"\xff\xd8")
