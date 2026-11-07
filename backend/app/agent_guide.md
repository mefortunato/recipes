# Submitting recipes to Gourmet Vault (guide for AI agents)

You are helping a person write recipes. When they say they like a recipe and want to keep it,
save it to their Gourmet Vault recipe book with the HTTP API below.

- **API base:** `{{API_BASE}}`
- **Auth:** send the person's API key as `Authorization: Bearer rbk_...` on every request.
  The person creates keys in the web app (account menu → *Agent API keys*). Never print the key
  back to the person or put it in the recipe.
- **Content-Type:** `application/json` for recipe requests.

## Before you submit

1. Show the person the final recipe and get a clear "yes, save it".
2. Check it isn't already there: `GET {{API_BASE}}/recipes?search=<title words>`.
   If it is, and they want it changed, update it (`PUT`) instead of creating a duplicate.

## Create a recipe

`POST {{API_BASE}}/recipes` → `201 Created` with the saved recipe (keep its `id` for later edits).

```bash
curl -sS -X POST "{{API_BASE}}/recipes" \
  -H "Authorization: Bearer $RECIPES_API_KEY" \
  -H "Content-Type: application/json" \
  -d @recipe.json
```

```json
{
  "title": "Charred Scallion Fried Rice",
  "description": "Day-old rice, crisped in a hot pan with charred scallions and a soy-butter finish.",
  "prep_time_minutes": 10,
  "cook_time_minutes": 15,
  "servings": 2,
  "difficulty": "Easy",
  "cuisine": "Chinese",
  "category": "Main Course",
  "tags": ["quick", "weeknight", "vegetarian"],
  "ingredients": [
    {"name": "cooked jasmine rice, chilled", "amount": 3, "unit": "cups"},
    {"name": "scallions", "amount": 6, "unit": "", "notes": "cut into 2 cm pieces"},
    {"name": "eggs", "amount": 2, "unit": ""},
    {"name": "soy sauce", "amount": 1.5, "unit": "tbsp"},
    {"name": "butter", "amount": 1, "unit": "tbsp"}
  ],
  "instructions": [
    {"step_number": 1, "instruction": "Char the scallions in a dry, very hot wok until blistered. Set aside."},
    {"step_number": 2, "instruction": "Scramble the eggs in a little oil, then add the rice and press it flat to crisp.", "tip": "Cold rice fries; warm rice steams."},
    {"step_number": 3, "instruction": "Toss in the scallions, soy sauce and butter, and serve hot."}
  ],
  "notes": "Their tweak: extra butter. Great with a fried egg on top."
}
```

### Fields

| Field | Type | Rules |
| --- | --- | --- |
| `title` | string | **required**, 2–150 chars |
| `description` | string | **required**, up to 1000 chars |
| `prep_time_minutes`, `cook_time_minutes` | integer | 0–10080 (defaults 15 / 30) |
| `servings` | integer | 1–100 (default 4). Ingredient amounts are for this many servings. |
| `difficulty` | string | exactly `"Easy"`, `"Medium"` or `"Hard"` |
| `cuisine`, `category` | string | up to 50 chars, e.g. `"Italian"`, `"Dessert"`. Reuse existing values from `GET {{API_BASE}}/recipes/meta/cuisines` and `/recipes/meta/categories` when one fits. |
| `tags` | string[] | up to 30, each up to 40 chars, stored lowercase. Existing tags: `GET {{API_BASE}}/recipes/meta/tags` |
| `ingredients` | object[] | up to 100: `name` (required), `amount` (**number > 0**, required), `unit` (may be `""`), `notes` (optional) |
| `instructions` | object[] | up to 100: `step_number` (1, 2, 3…), `instruction` (required), `tip` (optional) |
| `images` | string[] | up to 10 absolute `https://` URLs, or uploaded-photo URLs (see below) |
| `notes` | string | up to 5000 chars: pairings, substitutions, the story behind it |

`amount` must be a positive number so the app can scale servings: write "a pinch" as
`{"name": "salt", "amount": 1, "unit": "pinch"}`, and "salt to taste" as amount `1` with
`"notes": "to taste"`. Use decimals, not fractions (`0.5`, not `"1/2"`).

## Update a recipe

`PUT {{API_BASE}}/recipes/{id}` with only the fields to change. Lists (`ingredients`,
`instructions`, `tags`, `images`) are replaced whole, so send the complete new list.

## Add a photo (optional)

`POST {{API_BASE}}/images` as `multipart/form-data` with a `file` field (JPEG, PNG, WebP or GIF).
The response's `url` goes in the recipe's `images` list.

```bash
curl -sS -X POST "{{API_BASE}}/images" -H "Authorization: Bearer $RECIPES_API_KEY" -F "file=@dish.jpg"
```

## Errors

- `401` – the key is missing, mistyped or revoked: ask the person for a new key.
- `403` – the person's account can no longer edit recipes, or you tried something keys can't do
  (keys can't delete recipes or manage users).
- `422` – validation failed; the response's `detail` lists each bad field. Fix and retry.

When it worked, tell the person the recipe was saved and its title.
