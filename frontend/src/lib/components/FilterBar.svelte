<script>
  import {
    filters,
    categories,
    cuisines,
    loadRecipes,
    totalRecipes
  } from '../stores';

  const defaultCategories = ['All', 'Main Course', 'Salad', 'Dessert', 'Appetizer', 'Breakfast'];
  const difficulties = ['All', 'Easy', 'Medium', 'Hard'];
  const timePresets = [
    { label: 'Any Time', value: null },
    { label: '≤ 30 mins', value: 30 },
    { label: '≤ 45 mins', value: 45 },
    { label: '≤ 60 mins', value: 60 },
  ];

  function selectCategory(cat) {
    filters.update((f) => ({ ...f, category: cat }));
    loadRecipes();
  }

  function handleCuisineChange(e) {
    filters.update((f) => ({ ...f, cuisine: e.target.value }));
    loadRecipes();
  }

  function handleDifficultyChange(e) {
    filters.update((f) => ({ ...f, difficulty: e.target.value }));
    loadRecipes();
  }

  function selectMaxTime(val) {
    filters.update((f) => ({ ...f, max_time: val }));
    loadRecipes();
  }

  function toggleFavoriteOnly() {
    filters.update((f) => ({
      ...f,
      is_favorite: f.is_favorite === true ? null : true,
    }));
    loadRecipes();
  }

  function resetFilters() {
    filters.set({
      search: '',
      category: 'All',
      cuisine: 'All',
      difficulty: 'All',
      max_time: null,
      is_favorite: null,
      tag: null,
    });
    loadRecipes();
  }
</script>

<div class="filter-bar">
  <!-- Category Pills -->
  <div class="category-row">
    <div class="category-pills">
      {#each defaultCategories as cat}
        <button
          class="pill {($filters.category || 'All') === cat ? 'active' : ''}"
          on:click={() => selectCategory(cat)}
        >
          {cat}
        </button>
      {/each}
    </div>

    <div class="recipe-counter">
      <strong>{$totalRecipes}</strong> recipes found
    </div>
  </div>

  <!-- Detailed Filters Row -->
  <div class="secondary-filters">
    <!-- Cuisine Dropdown -->
    <div class="filter-item">
      <label for="cuisine-select" class="filter-label">Cuisine</label>
      <select
        id="cuisine-select"
        class="form-select filter-select"
        value={$filters.cuisine || 'All'}
        on:change={handleCuisineChange}
      >
        <option value="All">All Cuisines</option>
        {#each $cuisines as c}
          <option value={c}>{c}</option>
        {/each}
      </select>
    </div>

    <!-- Difficulty Dropdown -->
    <div class="filter-item">
      <label for="diff-select" class="filter-label">Difficulty</label>
      <select
        id="diff-select"
        class="form-select filter-select"
        value={$filters.difficulty || 'All'}
        on:change={handleDifficultyChange}
      >
        {#each difficulties as d}
          <option value={d}>{d === 'All' ? 'All Difficulties' : d}</option>
        {/each}
      </select>
    </div>

    <!-- Time Presets -->
    <div class="filter-item">
      <span class="filter-label">Max Cooking Time</span>
      <div class="time-pills">
        {#each timePresets as preset}
          <button
            class="time-pill {$filters.max_time === preset.value ? 'active' : ''}"
            on:click={() => selectMaxTime(preset.value)}
          >
            {preset.label}
          </button>
        {/each}
      </div>
    </div>

    <!-- Favorites Toggle -->
    <button
      class="btn btn-sm {$filters.is_favorite ? 'btn-primary' : 'btn-secondary'} fav-toggle"
      on:click={toggleFavoriteOnly}
    >
      <span>{$filters.is_favorite ? '❤️ Favorites Only' : '🤍 Favorites'}</span>
    </button>

    <!-- Reset Filter Button -->
    <button class="btn btn-ghost btn-sm reset-btn" on:click={resetFilters}>
      <span>Reset</span>
    </button>
  </div>
</div>

<style>
  .filter-bar {
    background-color: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 1.1rem 1.4rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow-sm);
  }

  .category-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
    padding-bottom: 0.85rem;
    border-bottom: 1px solid var(--border-subtle);
    flex-wrap: wrap;
  }

  .category-pills {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .pill {
    padding: 0.4rem 0.9rem;
    border-radius: 9999px;
    font-size: 0.85rem;
    font-weight: 600;
    font-family: var(--font-sans);
    background-color: var(--bg-subtle);
    border: 1px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .pill:hover {
    background-color: #eee9e0;
    color: var(--text-main);
  }

  .pill.active {
    background-color: var(--primary);
    color: white;
    box-shadow: 0 2px 5px var(--primary-glow);
  }

  .recipe-counter {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .recipe-counter strong {
    color: var(--text-main);
    font-weight: 700;
  }

  .secondary-filters {
    display: flex;
    align-items: center;
    gap: 1.2rem;
    flex-wrap: wrap;
  }

  .filter-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .filter-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .filter-select {
    padding: 0.35rem 0.75rem;
    font-size: 0.82rem;
    width: auto;
    min-width: 120px;
  }

  .time-pills {
    display: flex;
    gap: 0.35rem;
  }

  .time-pill {
    padding: 0.3rem 0.65rem;
    font-size: 0.78rem;
    border-radius: var(--radius-sm);
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .time-pill:hover {
    background: #e7e4dc;
  }

  .time-pill.active {
    background: var(--text-main);
    color: white;
    border-color: var(--text-main);
  }

  .fav-toggle {
    margin-left: auto;
  }

  .reset-btn {
    text-decoration: underline;
    font-size: 0.8rem;
  }

  @media (max-width: 800px) {
    .fav-toggle {
      margin-left: 0;
    }
  }
</style>
