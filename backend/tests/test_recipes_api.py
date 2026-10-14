import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_probes(async_client: AsyncClient):
    # Test liveness probe
    live_resp = await async_client.get("/health/live")
    assert live_resp.status_code == 200
    assert live_resp.json()["status"] == "ok"

    # Test readiness probe
    ready_resp = await async_client.get("/health/ready")
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert "status" in resp.json()
    assert resp.json()["status"] == "online"


@pytest.mark.asyncio
async def test_list_recipes(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/recipes")
    assert resp.status_code == 200
    data = resp.json()
    assert "recipes" in data
    assert "total" in data
    assert data["total"] >= 1
    assert len(data["recipes"]) >= 1


@pytest.mark.asyncio
async def test_recipe_filtering(async_client: AsyncClient):
    # Filter by cuisine
    resp = await async_client.get("/api/v1/recipes?cuisine=Italian")
    assert resp.status_code == 200
    data = resp.json()
    for recipe in data["recipes"]:
        assert recipe["cuisine"].lower() == "italian"


@pytest.mark.asyncio
async def test_create_and_get_recipe(async_client: AsyncClient):
    new_recipe = {
        "title": "Creamy Mushroom Risotto",
        "description": "Rich Arborio rice simmered slowly with white wine, vegetable broth, and sautéed cremini mushrooms.",
        "prep_time_minutes": 10,
        "cook_time_minutes": 25,
        "servings": 4,
        "difficulty": "Medium",
        "cuisine": "Italian",
        "category": "Main Course",
        "tags": ["vegetarian", "comfort-food", "italian"],
        "ingredients": [
            {"name": "Arborio rice", "amount": 300, "unit": "g", "notes": "uncooked"},
            {"name": "Vegetable broth", "amount": 4, "unit": "cups", "notes": "warm"},
            {"name": "Cremini mushrooms", "amount": 250, "unit": "g", "notes": "sliced"},
            {"name": "Dry white wine", "amount": 0.5, "unit": "cup"},
        ],
        "instructions": [
            {"step_number": 1, "instruction": "Sauté mushrooms in olive oil until golden brown.", "tip": "Don't salt until browned."},
            {"step_number": 2, "instruction": "Toast arborio rice in butter and deglaze with wine."},
            {"step_number": 3, "instruction": "Gradually add warm broth ladle by ladle while stirring constantly until creamy."},
        ],
        "images": [
            "https://images.unsplash.com/photo-1633964913295-ceb43826e7c9?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1600891964599-f61ba0e24092?auto=format&fit=crop&w=1200&q=80",
        ],
        "image_url": "https://images.unsplash.com/photo-1633964913295-ceb43826e7c9?auto=format&fit=crop&w=1200&q=80",
        "is_favorite": True,
    }

    create_resp = await async_client.post("/api/v1/recipes", json=new_recipe)
    assert create_resp.status_code == 201
    created = create_resp.json()
    recipe_id = created["id"]
    assert created["title"] == "Creamy Mushroom Risotto"
    assert created["total_time_minutes"] == 35
    assert "nutrition" not in created
    assert len(created["images"]) == 2
    assert created["image_url"] == created["images"][0]

    # Retrieve by ID
    get_resp = await async_client.get(f"/api/v1/recipes/{recipe_id}")
    assert get_resp.status_code == 200
    retrieved = get_resp.json()
    assert retrieved["id"] == recipe_id
    assert "nutrition" not in retrieved
    assert len(retrieved["images"]) == 2


@pytest.mark.asyncio
async def test_scale_recipe(async_client: AsyncClient):
    list_resp = await async_client.get("/api/v1/recipes")
    recipes = list_resp.json()["recipes"]
    recipe = recipes[0]
    recipe_id = recipe["id"]
    original_servings = recipe["servings"]

    target_servings = original_servings * 2
    scale_resp = await async_client.get(f"/api/v1/recipes/{recipe_id}/scale?servings={target_servings}")
    assert scale_resp.status_code == 200
    scaled = scale_resp.json()
    assert scaled["original_servings"] == original_servings
    assert scaled["target_servings"] == target_servings
    assert scaled["scale_multiplier"] == 2.0

    # Ensure ingredient amounts doubled
    for orig_ing, scaled_ing in zip(recipe["ingredients"], scaled["ingredients"]):
        assert scaled_ing["scaled_amount"] == pytest.approx(orig_ing["amount"] * 2.0, rel=1e-2)


@pytest.mark.asyncio
async def test_update_and_delete_recipe(async_client: AsyncClient):
    list_resp = await async_client.get("/api/v1/recipes")
    recipe = list_resp.json()["recipes"][0]
    recipe_id = recipe["id"]

    # Partial update
    update_resp = await async_client.put(
        f"/api/v1/recipes/{recipe_id}",
        json={"title": "Updated Recipe Title", "is_favorite": True},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Recipe Title"

    # Delete
    del_resp = await async_client.delete(f"/api/v1/recipes/{recipe_id}")
    assert del_resp.status_code == 204

    # Verify 404 on deleted
    not_found_resp = await async_client.get(f"/api/v1/recipes/{recipe_id}")
    assert not_found_resp.status_code == 404


@pytest.mark.asyncio
async def test_multiple_images_support(async_client: AsyncClient):
    # 1. Create a recipe with 3 images
    recipe_data = {
        "title": "Multi-Image Berry Tart",
        "description": "Crisp pastry crust filled with vanilla pastry cream and topped with fresh berries.",
        "prep_time_minutes": 20,
        "cook_time_minutes": 25,
        "servings": 6,
        "ingredients": [
            {"name": "Tart crust", "amount": 1, "unit": "crust"},
            {"name": "Pastry cream", "amount": 2, "unit": "cups"},
            {"name": "Mixed fresh berries", "amount": 3, "unit": "cups"},
        ],
        "instructions": [
            {"step_number": 1, "instruction": "Bake tart crust until golden brown."},
            {"step_number": 2, "instruction": "Spread chilled pastry cream into cooled shell."},
            {"step_number": 3, "instruction": "Arrange fresh berries decoratively on top."},
        ],
        "images": [
            "https://images.unsplash.com/photo-1519869325930-281384150729?w=800",
            "https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=800",
            "https://images.unsplash.com/photo-1464349095431-e9a21285b5f3?w=800",
        ],
    }

    resp = await async_client.post("/api/v1/recipes", json=recipe_data)
    assert resp.status_code == 201
    created = resp.json()
    assert len(created["images"]) == 3
    # Check that image_url defaults to first image
    assert created["image_url"] == created["images"][0]
    assert "nutrition" not in created
    recipe_id = created["id"]

    # 2. Update images list
    new_images = [
        "https://images.unsplash.com/photo-1587314168485-3236d6710814?w=800",
        "https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=800",
    ]
    update_resp = await async_client.put(
        f"/api/v1/recipes/{recipe_id}",
        json={"images": new_images},
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["images"] == new_images
    assert updated["image_url"] == new_images[0]
    assert "nutrition" not in updated


@pytest.mark.asyncio
async def test_static_html_and_spa_fallback(async_client: AsyncClient):
    # Test browser GET on root returns HTML
    resp_browser = await async_client.get("/", headers={"accept": "text/html,application/xhtml+xml"})
    assert resp_browser.status_code == 200
    assert "text/html" in resp_browser.headers.get("content-type", "")

    # Test client-side route fallback to SPA index.html
    resp_spa = await async_client.get("/recipes/view/123")
    assert resp_spa.status_code == 200
    assert "text/html" in resp_spa.headers.get("content-type", "")

    # Test non-existent API route returns 404 JSON
    resp_api_404 = await async_client.get("/api/v1/nonexistent")
    assert resp_api_404.status_code == 404

