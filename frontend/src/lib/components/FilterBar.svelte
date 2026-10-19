<script>
  import {
    filters,
    categories,
    cuisines,
    tags,
    loadRecipes,
    totalRecipes,
    currentUser,
    isAuthModalOpen,
    showToast
  } from '../stores';

  let isFilterModalOpen = false;

  const defaultCategories = ['All', 'Main Course', 'Salad', 'Dessert', 'Appetizer', 'Breakfast'];
  const difficulties = ['All', 'Easy', 'Medium', 'Hard'];
  const timePresets = [
    { label: 'Any Time', value: null },
    { label: '≤ 30 mins', value: 30 },
    { label: '≤ 45 mins', value: 45 },
    { label: '≤ 60 mins', value: 60 },
  ];

  const sortOptions = [
    { label: '⭐ Top Rated (Votes)', sort_by: 'aggregate_rating', sort_order: -1 },
    { label: '👍 Most Upvotes', sort_by: 'upvotes_count', sort_order: -1 },
    { label: '🕒 Newest First', sort_by: 'created_at', sort_order: -1 },
    { label: '⚡ Quickest Cook', sort_by: 'cook_time_minutes', sort_order: 1 },
    { label: '🔤 Title (A–Z)', sort_by: 'title', sort_order: 1 },
  ];

  function openFilterModal() {
    isFilterModalOpen = true;
  }

  function closeFilterModal() {
    isFilterModalOpen = false;
  }

  function handleKeydown(e) {
    if (e.key === 'Escape' && isFilterModalOpen) {
      closeFilterModal();
    }
  }

  function selectCategory(cat) {
    filters.update((f) => ({ ...f, category: cat }));
    loadRecipes();
  }

  function selectCuisine(c) {
    filters.update((f) => ({ ...f, cuisine: c }));
    loadRecipes();
  }

  function selectDifficulty(diff) {
    filters.update((f) => ({ ...f, difficulty: diff }));
    loadRecipes();
  }

  function selectMaxTime(val) {
    filters.update((f) => ({ ...f, max_time: val }));
    loadRecipes();
  }

  function selectSort(sort_by, sort_order) {
    filters.update((f) => ({ ...f, sort_by, sort_order }));
    loadRecipes();
  }

  function handleSortChange(e) {
    const parts = e.target.value.split(':');
    const sort_by = parts[0];
    const sort_order = parseInt(parts[1], 10);
    filters.update((f) => ({ ...f, sort_by, sort_order }));
    loadRecipes();
  }

  function toggleUpvotedOnly() {
    if (!$currentUser) {
      showToast('Sign in to filter recipes you have upvoted.', 'info');
      isAuthModalOpen.set(true);
      return;
    }
    filters.update((f) => ({
      ...f,
      user_voted: f.user_voted === 'up' ? null : 'up',
    }));
    loadRecipes();
  }

  function selectTag(t) {
    filters.update((f) => ({
      ...f,
      tag: f.tag === t ? null : t,
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
      user_voted: null,
      sort_by: 'created_at',
      sort_order: -1,
      tag: null,
    });
    loadRecipes();
  }

  $: activeFilterCount = (
    ($filters.cuisine && $filters.cuisine !== 'All' ? 1 : 0) +
    ($filters.difficulty && $filters.difficulty !== 'All' ? 1 : 0) +
    ($filters.max_time ? 1 : 0) +
    ($filters.tag ? 1 : 0)
  );

  $: currentSortVal = `${$filters.sort_by || 'created_at'}:${$filters.sort_order ?? -1}`;
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="filter-bar">
  <!-- Category Pills Row -->
  <div class="category-row">
    <div class="category-pills">
      {#each defaultCategories as cat}
        <button
          type="button"
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

  <!-- Simplified Controls Row -->
  <div class="controls-row">
    <!-- Sort By Dropdown -->
    <div class="filter-item">
      <label for="sort-select" class="filter-label">Sort By</label>
      <select
        id="sort-select"
        class="form-select filter-select sort-select"
        value={currentSortVal}
        on:change={handleSortChange}
      >
        {#each sortOptions as opt}
          <option value={`${opt.sort_by}:${opt.sort_order}`}>{opt.label}</option>
        {/each}
      </select>
    </div>

    <!-- Filter Modal Trigger Button -->
    <button
      type="button"
      class="btn btn-sm {activeFilterCount > 0 ? 'btn-primary' : 'btn-secondary'} filter-modal-btn"
      on:click={openFilterModal}
      title="Open all filter and sort options"
    >
      <span class="filter-icon">⚙️</span>
      <span>Filters</span>
      {#if activeFilterCount > 0}
        <span class="filter-badge">{activeFilterCount}</span>
      {/if}
    </button>

    <!-- My Upvoted Toggle Button -->
    <button
      type="button"
      class="btn btn-sm {$filters.user_voted === 'up' ? 'btn-primary' : 'btn-secondary'} vote-filter-btn"
      on:click={toggleUpvotedOnly}
      title="Filter recipes you have upvoted"
    >
      <span>{$filters.user_voted === 'up' ? '👍 Upvoted by Me' : '👍 My Upvoted'}</span>
    </button>
  </div>
</div>

<!-- Filter Options Modal -->
{#if isFilterModalOpen}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-noninteractive-element-interactions -->
  <div
    class="modal-backdrop"
    on:click={closeFilterModal}
    role="dialog"
    aria-modal="true"
    aria-labelledby="filter-modal-title"
    tabindex="-1"
  >
    <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-noninteractive-element-interactions -->
    <div
      class="filter-modal-card animate-fade-in"
      on:click|stopPropagation
      role="document"
    >
      <!-- Modal Header -->
      <div class="modal-header">
        <div class="modal-header-text">
          <div class="modal-icon-title">
            <span class="header-icon">⚙️</span>
            <h2 id="filter-modal-title" class="modal-title">Filter & Sort Options</h2>
          </div>
          <p class="modal-subtitle">Fine-tune your recipe vault by cuisine, rating, time, difficulty, and more.</p>
        </div>
        <button
          type="button"
          class="modal-close-btn"
          on:click={closeFilterModal}
          aria-label="Close filters modal"
        >
          ✕
        </button>
      </div>

      <!-- Modal Body -->
      <div class="modal-body">
        <!-- 1. Sort Options -->
        <div class="filter-group">
          <span class="group-title">Sort By</span>
          <div class="option-pills-row">
            {#each sortOptions as opt}
              <button
                type="button"
                class="option-pill {currentSortVal === `${opt.sort_by}:${opt.sort_order}` ? 'active' : ''}"
                on:click={() => selectSort(opt.sort_by, opt.sort_order)}
              >
                {opt.label}
              </button>
            {/each}
          </div>
        </div>

        <!-- 2. User Voting Filter -->
        <div class="filter-group">
          <span class="group-title">User Upvotes</span>
          <div class="option-pills-row">
            <button
              type="button"
              class="option-pill {$filters.user_voted === 'up' ? 'active' : ''}"
              on:click={toggleUpvotedOnly}
            >
              <span>👍 {$filters.user_voted === 'up' ? 'Filtering: My Upvoted Recipes' : 'Only My Upvoted Recipes'}</span>
            </button>
            {#if $filters.user_voted}
              <button
                type="button"
                class="option-pill"
                on:click={() => { filters.update(f => ({ ...f, user_voted: null })); loadRecipes(); }}
              >
                Show All Recipes
              </button>
            {/if}
          </div>
        </div>

        <!-- 3. Category -->
        <div class="filter-group">
          <span class="group-title">Meal Category</span>
          <div class="option-pills-row">
            {#each defaultCategories as cat}
              <button
                type="button"
                class="option-pill {($filters.category || 'All') === cat ? 'active' : ''}"
                on:click={() => selectCategory(cat)}
              >
                {cat}
              </button>
            {/each}
          </div>
        </div>

        <!-- 4. Cuisine Selection -->
        <div class="filter-group">
          <span class="group-title">Cuisine</span>
          <div class="option-pills-row">
            <button
              type="button"
              class="option-pill {(!$filters.cuisine || $filters.cuisine === 'All') ? 'active' : ''}"
              on:click={() => selectCuisine('All')}
            >
              All Cuisines
            </button>
            {#each $cuisines as c}
              <button
                type="button"
                class="option-pill {$filters.cuisine === c ? 'active' : ''}"
                on:click={() => selectCuisine(c)}
              >
                {c}
              </button>
            {/each}
          </div>
        </div>

        <!-- 5. Difficulty Level -->
        <div class="filter-group">
          <span class="group-title">Difficulty</span>
          <div class="option-pills-row">
            {#each difficulties as d}
              <button
                type="button"
                class="option-pill {($filters.difficulty || 'All') === d ? 'active' : ''}"
                on:click={() => selectDifficulty(d)}
              >
                {d === 'All' ? 'All Difficulties' : d}
              </button>
            {/each}
          </div>
        </div>

        <!-- 6. Max Cooking Time -->
        <div class="filter-group">
          <span class="group-title">Max Cooking Time</span>
          <div class="option-pills-row">
            {#each timePresets as preset}
              <button
                type="button"
                class="option-pill {$filters.max_time === preset.value ? 'active' : ''}"
                on:click={() => selectMaxTime(preset.value)}
              >
                {preset.label}
              </button>
            {/each}
          </div>
        </div>

        <!-- 7. Dietary & Recipe Tags -->
        {#if $tags && $tags.length > 0}
          <div class="filter-group">
            <span class="group-title">Dietary & Recipe Tags</span>
            <div class="option-pills-row tags-scrollable">
              {#each $tags as t}
                <button
                  type="button"
                  class="option-pill tag-opt {$filters.tag === t ? 'active' : ''}"
                  on:click={() => selectTag(t)}
                >
                  #{t}
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      <!-- Modal Footer -->
      <div class="modal-footer">
        <button
          type="button"
          class="btn btn-ghost btn-sm reset-all-btn"
          on:click={resetFilters}
        >
          <span>↺ Reset All Filters</span>
        </button>

        <div class="footer-right">
          <button
            type="button"
            class="btn btn-primary"
            on:click={closeFilterModal}
          >
            Show {$totalRecipes} {$totalRecipes === 1 ? 'Recipe' : 'Recipes'}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

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

  /* Simplified Controls Row */
  .controls-row {
    display: flex;
    align-items: center;
    gap: 1rem;
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
    padding: 0.4rem 0.85rem;
    font-size: 0.85rem;
    width: auto;
  }

  .sort-select {
    min-width: 175px;
    font-weight: 600;
    background-color: var(--bg-surface);
    border-color: #cbd5e1;
  }

  .filter-modal-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-weight: 600;
    padding: 0.4rem 0.95rem;
  }

  .filter-badge {
    background: #ef4444;
    color: #ffffff;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 0.1rem 0.45rem;
    border-radius: 9999px;
    line-height: 1.2;
  }

  .vote-filter-btn {
    margin-left: auto;
    font-weight: 600;
  }


  /* Modal Backdrop & Overlay */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(4px);
    z-index: 60;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    overflow-y: auto;
  }

  .filter-modal-card {
    background: var(--bg-surface);
    width: 100%;
    max-width: 620px;
    max-height: 85vh;
    border-radius: var(--radius-xl);
    overflow: hidden;
    position: relative;
    box-shadow: var(--shadow-xl);
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border-color);
  }

  .modal-header {
    padding: 1.35rem 1.75rem 1.15rem;
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    background: linear-gradient(180deg, var(--bg-subtle) 0%, var(--bg-surface) 100%);
  }

  .modal-header-text {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .modal-icon-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .header-icon {
    font-size: 1.25rem;
  }

  .modal-title {
    font-family: var(--font-serif);
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text-main);
    letter-spacing: -0.01em;
  }

  .modal-subtitle {
    font-size: 0.82rem;
    color: var(--text-muted);
  }

  .modal-close-btn {
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    color: var(--text-muted);
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-size: 0.95rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .modal-close-btn:hover {
    background: #e2e8f0;
    color: var(--text-main);
  }

  .modal-body {
    padding: 1.5rem 1.75rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1.35rem;
  }

  .filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .group-title {
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .option-pills-row {
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
  }

  .tags-scrollable {
    max-height: 130px;
    overflow-y: auto;
    padding-right: 0.25rem;
  }

  .option-pill {
    padding: 0.35rem 0.8rem;
    font-size: 0.82rem;
    font-weight: 600;
    font-family: var(--font-sans);
    border-radius: var(--radius-sm);
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    color: var(--text-main);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .option-pill:hover {
    background: #eae6de;
    border-color: #cbd5e1;
  }

  .option-pill.active {
    background: var(--primary);
    color: #ffffff;
    border-color: var(--primary);
    box-shadow: 0 2px 4px var(--primary-glow);
  }

  .tag-opt {
    font-size: 0.78rem;
    padding: 0.25rem 0.65rem;
  }

  .modal-footer {
    padding: 1rem 1.75rem;
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .reset-all-btn {
    color: #ef4444;
    font-weight: 600;
  }

  .reset-all-btn:hover {
    background: #fee2e2;
    color: #b91c1c;
  }

  @media (max-width: 800px) {
    .vote-filter-btn {
      margin-left: 0;
    }
    .modal-footer {
      flex-direction: column-reverse;
      align-items: stretch;
    }
    .footer-right {
      display: flex;
    }
    .footer-right button {
      width: 100%;
    }
  }
</style>


