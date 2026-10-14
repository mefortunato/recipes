<script>
  import { activeRecipe, isViewModalOpen, showToast, loadRecipes, currentUser, isAuthModalOpen } from '../stores';
  import { api } from '../api';

  export let recipe;

  let imageError = false;
  let togglingFavorite = false;

  function openDetails() {
    activeRecipe.set(recipe);
    isViewModalOpen.set(true);
  }

  async function toggleFavorite(e) {
    e.stopPropagation();
    if (!$currentUser?.can_edit) {
      showToast('Sign in as an authorized editor to save favorites.', 'info');
      isAuthModalOpen.set(true);
      return;
    }
    if (togglingFavorite) return;
    togglingFavorite = true;
    try {
      const updated = await api.updateRecipe(recipe.id, {
        is_favorite: !recipe.is_favorite,
      });
      recipe.is_favorite = updated.is_favorite;
      showToast(
        recipe.is_favorite ? 'Added to favorites' : 'Removed from favorites',
        'info',
        2000
      );
    } catch (err) {
      showToast('Could not update favorite status', 'error');
    } finally {
      togglingFavorite = false;
    }
  }

  function getDifficultyBadge(diff) {
    if (diff === 'Easy') return 'badge-green';
    if (diff === 'Medium') return 'badge-amber';
    return 'badge-purple';
  }

  $: primaryImage = (recipe.images && recipe.images.length > 0) ? recipe.images[0] : (recipe.image_url || '');
  $: imageCount = (recipe.images && recipe.images.length > 0) ? recipe.images.length : (recipe.image_url ? 1 : 0);
</script>

<div class="recipe-card" on:click={openDetails} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && openDetails()}>
  <!-- Card Header & Image -->
  <div class="card-media">
    {#if primaryImage && !imageError}
      <img
        src={primaryImage}
        alt={recipe.title}
        class="recipe-img"
        on:error={() => (imageError = true)}
        loading="lazy"
      />
    {:else}
      <div class="fallback-img">
        <span class="fallback-icon">🥘</span>
      </div>
    {/if}

    <!-- Photo count indicator badge -->
    {#if imageCount > 1}
      <div class="photo-count-badge" title="{imageCount} photos available">
        <span class="photo-icon">📷</span>
        <span>{imageCount}</span>
      </div>
    {/if}

    <!-- Favorite floating button -->
    <button
      class="fav-btn {recipe.is_favorite ? 'fav-active' : ''}"
      on:click={toggleFavorite}
      title={recipe.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
      aria-label="Toggle favorite"
    >
      {recipe.is_favorite ? '❤️' : '🤍'}
    </button>

    <!-- Difficulty & Cuisine Badges -->
    <div class="media-badges">
      <span class="badge {getDifficultyBadge(recipe.difficulty)}">
        {recipe.difficulty}
      </span>
      <span class="badge badge-gray">
        {recipe.cuisine}
      </span>
    </div>
  </div>

  <!-- Card Body -->
  <div class="card-body">
    <div class="category-meta">{recipe.category}</div>
    <h3 class="recipe-title">{recipe.title}</h3>
    <p class="recipe-desc">{recipe.description}</p>

    <!-- Key Metrics -->
    <div class="recipe-metrics">
      <div class="metric" title="Total cooking duration">
        <span class="metric-icon">⏱️</span>
        <span class="metric-val">{recipe.total_time_minutes}m</span>
      </div>
      <div class="metric" title="Portions">
        <span class="metric-icon">👥</span>
        <span class="metric-val">{recipe.servings} servings</span>
      </div>
      <div class="metric" title="Number of ingredients">
        <span class="metric-icon">🥕</span>
        <span class="metric-val">{recipe.ingredients ? recipe.ingredients.length : 0} items</span>
      </div>
    </div>

    <!-- Tags -->
    {#if recipe.tags && recipe.tags.length > 0}
      <div class="tags-row">
        {#each recipe.tags.slice(0, 3) as tag}
          <span class="tag-pill">#{tag}</span>
        {/each}
        {#if recipe.tags.length > 3}
          <span class="tag-more">+{recipe.tags.length - 3}</span>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .recipe-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    cursor: pointer;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease, border-color 0.2s ease;
    box-shadow: var(--shadow-sm);
    position: relative;
  }

  .recipe-card:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-xl);
    border-color: #d6d3d1;
  }

  .card-media {
    position: relative;
    width: 100%;
    height: 195px;
    background-color: var(--bg-subtle);
    overflow: hidden;
  }

  .recipe-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 0.3s ease;
  }

  .recipe-card:hover .recipe-img {
    transform: scale(1.04);
  }

  .fallback-img {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #e6f4f6 0%, #c5e8eb 100%);
  }

  .fallback-icon {
    font-size: 3.5rem;
  }

  .photo-count-badge {
    position: absolute;
    top: 0.75rem;
    left: 0.75rem;
    background: rgba(15, 23, 42, 0.75);
    backdrop-filter: blur(6px);
    color: #ffffff;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 0.25rem 0.55rem;
    border-radius: 9999px;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
    z-index: 2;
    letter-spacing: 0.02em;
    border: 1px solid rgba(255, 255, 255, 0.2);
  }

  .fav-btn {
    position: absolute;
    top: 0.75rem;
    right: 0.75rem;
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(4px);
    border: none;
    border-radius: 50%;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 1.1rem;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
    transition: transform 0.15s ease, background 0.15s ease;
  }

  .fav-btn:hover {
    transform: scale(1.15);
    background: #ffffff;
  }

  .media-badges {
    position: absolute;
    bottom: 0.75rem;
    left: 0.75rem;
    display: flex;
    gap: 0.4rem;
  }

  .card-body {
    padding: 1.15rem;
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  .category-meta {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--primary);
    margin-bottom: 0.3rem;
  }

  .recipe-title {
    font-family: var(--font-serif);
    font-size: 1.25rem;
    font-weight: 700;
    line-height: 1.25;
    color: var(--text-main);
    margin-bottom: 0.5rem;
  }

  .recipe-desc {
    font-size: 0.85rem;
    color: var(--text-muted);
    line-height: 1.45;
    margin-bottom: 1rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .recipe-metrics {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding-top: 0.85rem;
    border-top: 1px solid var(--border-subtle);
    margin-top: auto;
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .metric {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  .metric-val {
    font-weight: 600;
    color: var(--text-main);
  }

  .tags-row {
    display: flex;
    gap: 0.35rem;
    margin-top: 0.75rem;
    flex-wrap: wrap;
  }

  .tag-pill {
    font-size: 0.72rem;
    background-color: var(--bg-subtle);
    color: var(--text-muted);
    padding: 0.15rem 0.45rem;
    border-radius: var(--radius-sm);
  }

  .tag-more {
    font-size: 0.72rem;
    color: var(--text-light);
    padding: 0.15rem 0.25rem;
  }
</style>
