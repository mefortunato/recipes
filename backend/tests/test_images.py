import io

import pytest
from PIL import Image

from app.config import get_settings
from app.main import app

API = "/api/v1"


def make_image(width: int, height: int, fmt: str = "JPEG", mode: str = "RGB", noise: bool = False) -> bytes:
    if noise:
        import os
        image = Image.frombytes(mode, (width, height), os.urandom(width * height * len(mode)))
    else:
        image = Image.new(mode, (width, height), (200, 120, 40) if mode == "RGB" else (200, 120, 40, 128))
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


async def upload(client, data: bytes, filename: str = "photo.jpg", content_type: str = "image/jpeg"):
    return await client.post(f"{API}/images", files={"file": (filename, data, content_type)})


def recipe_payload(images):
    return {
        "title": "Uploaded Photo Pie",
        "description": "Has an uploaded photo",
        "ingredients": [{"name": "Flour", "amount": 1, "unit": "cup"}],
        "instructions": [{"step_number": 1, "instruction": "Bake it"}],
        "images": images,
    }


async def test_upload_large_image_is_scaled_down_and_served(async_client, setup_test_db):
    original = make_image(4000, 3000, noise=True)
    resp = await upload(async_client, original)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    settings = get_settings()
    assert max(body["width"], body["height"]) <= settings.image_max_dimension
    assert body["width"] / body["height"] == pytest.approx(4 / 3, rel=0.01)
    assert body["size_bytes"] <= settings.image_max_stored_bytes
    assert body["original_size_bytes"] == len(original)
    assert body["url"] == f"{API}/images/{body['id']}"

    stored = await setup_test_db["images"].find_one({})
    assert len(stored["data"]) == body["size_bytes"]
    assert stored["attached"] is False

    served = await async_client.get(body["url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"
    assert "immutable" in served.headers["cache-control"]
    assert Image.open(io.BytesIO(served.content)).size == (body["width"], body["height"])


async def test_small_png_with_alpha_keeps_size_and_transparency(async_client):
    resp = await upload(async_client, make_image(300, 200, fmt="PNG", mode="RGBA"), "a.png", "image/png")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert (body["width"], body["height"]) == (300, 200)
    served = await async_client.get(body["url"])
    assert Image.open(io.BytesIO(served.content)).mode == "RGBA"


async def test_exif_is_stripped_and_orientation_applied(async_client):
    image = Image.new("RGB", (400, 200), (10, 20, 30))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° on display
    exif[0x010F] = "SecretCam"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    resp = await upload(async_client, buffer.getvalue())
    body = resp.json()
    assert (body["width"], body["height"]) == (200, 400)
    served = await async_client.get(body["url"])
    assert not Image.open(io.BytesIO(served.content)).getexif()


async def test_rejects_non_images(async_client, setup_test_db):
    resp = await upload(async_client, b"<script>alert(1)</script>", "x.jpg")
    assert resp.status_code == 422
    resp = await upload(async_client, b"", "x.jpg")
    assert resp.status_code == 422
    assert await setup_test_db["images"].count_documents({}) == 0


async def test_rejects_oversized_upload(async_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "image_upload_max_bytes", 10_000)
    resp = await upload(async_client, make_image(1000, 1000, noise=True))
    assert resp.status_code == 413


async def test_rejects_decompression_bomb(async_client, monkeypatch):
    monkeypatch.setattr(get_settings(), "image_max_source_pixels", 1_000_000)
    resp = await upload(async_client, make_image(2000, 2000, fmt="PNG"), "bomb.png", "image/png")
    assert resp.status_code == 422


async def test_upload_requires_editor():
    from httpx import ASGITransport, AsyncClient
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await upload(client, make_image(10, 10))
    assert resp.status_code == 401


async def test_unknown_image_is_404(async_client):
    assert (await async_client.get(f"{API}/images/507f1f77bcf86cd799439011")).status_code == 404
    assert (await async_client.get(f"{API}/images/not-an-id")).status_code == 404


async def test_recipe_accepts_uploaded_paths_but_not_other_relative_urls(async_client):
    url = (await upload(async_client, make_image(50, 50))).json()["url"]
    resp = await async_client.post(f"{API}/recipes", json=recipe_payload([url]))
    assert resp.status_code == 201, resp.text
    assert resp.json()["image_url"] == url

    for bad in ("/etc/passwd", f"{API}/images/../recipes", "/api/v1/images/xyz", "javascript:alert(1)"):
        resp = await async_client.post(f"{API}/recipes", json=recipe_payload([bad]))
        assert resp.status_code == 422, bad


async def test_image_lifecycle_follows_recipes(async_client, setup_test_db):
    images = setup_test_db["images"]
    first = (await upload(async_client, make_image(50, 50))).json()
    second = (await upload(async_client, make_image(60, 60))).json()

    recipe = (await async_client.post(f"{API}/recipes", json=recipe_payload([first["url"], second["url"]]))).json()
    assert await images.count_documents({"attached": True}) == 2

    # Removing a photo from the recipe deletes it
    resp = await async_client.put(f"{API}/recipes/{recipe['id']}", json={"images": [second["url"]]})
    assert resp.status_code == 200
    assert (await async_client.get(first["url"])).status_code == 404
    assert (await async_client.get(second["url"])).status_code == 200

    # A photo shared with another recipe survives deleting one of them
    other = (await async_client.post(f"{API}/recipes", json=recipe_payload([second["url"]]))).json()
    assert (await async_client.delete(f"{API}/recipes/{recipe['id']}")).status_code == 204
    assert (await async_client.get(second["url"])).status_code == 200

    assert (await async_client.delete(f"{API}/recipes/{other['id']}")).status_code == 204
    assert (await async_client.get(second["url"])).status_code == 404
    assert await images.count_documents({}) == 0
