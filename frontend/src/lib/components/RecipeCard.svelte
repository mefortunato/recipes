<script>
  import {
    activeRecipe,
    isViewModalOpen,
    showToast,
    currentUser,
    isAuthModalOpen,
    updateRecipeInStore
  } from '../stores';
  import { api } from '../api';

  export let recipe;

  let imageError = false;
  let voting = false;
  let currentImageIndex = 0;

  $: recipeImages = (recipe.images && recipe.images.length > 0)
    ? recipe.images
    : (recipe.image_url ? [recipe.image_url] : []);
  $: totalImages = recipeImages.length;
  $: activeImage = recipeImages[currentImageIndex] || '';

  // Reset image index if out of range when recipe changes
  $: if (currentImageIndex >= totalImages && totalImages > 0) {
    currentImageIndex = 0;
  }

  function nextImage(e) {
    e.stopPropagation();
    if (totalImages <= 1) return;
    imageError = false;
    currentImageIndex = (currentImageIndex + 1) % totalImages;
  }

  function prevImage(e) {
    e.stopPropagation();
    if (totalImages <= 1) return;
    imageError = false;
    currentImageIndex = (currentImageIndex - 1 + totalImages) % totalImages;
  }

  function selectImage(idx, e) {
    e.stopPropagation();
    if (currentImageIndex === idx) return;
    imageError = false;
    currentImageIndex = idx;
  }

  function openDetails() {
    activeRecipe.set(recipe);
    isViewModalOpen.set(true);
  }

  async function handleUpvote(e) {
    e.stopPropagation();
    if (!$currentUser) {
      showToast('Please sign in to vote on recipes.', 'info');
      isAuthModalOpen.set(true);
      return;
    }
    if (voting) return;
    voting = true;
    try {
      const targetVote = recipe.user_vote === 1 ? 0 : 1;
      const updated = await api.voteRecipe(recipe.id, targetVote);
      recipe = { ...recipe, ...updated };
      updateRecipeInStore(updated);
      showToast(
        targetVote === 1 ? 'Upvoted recipe! 👍' : 'Upvote removed',
        'info',
        1800
      );
    } catch (err) {
      showToast(err.message || 'Could not register vote', 'error');
    } finally {
      voting = false;
    }
  }

  async function handleDownvote(e) {
    e.stopPropagation();
    if (!$currentUser) {
      showToast('Please sign in to vote on recipes.', 'info');
      isAuthModalOpen.set(true);
      return;
    }
    if (voting) return;
    voting = true;
    try {
      const targetVote = recipe.user_vote === -1 ? 0 : -1;
      const updated = await api.voteRecipe(recipe.id, targetVote);
      recipe = { ...recipe, ...updated };
      updateRecipeInStore(updated);
      showToast(
        targetVote === -1 ? 'Downvoted recipe 👎' : 'Downvote removed',
        'info',
        1800
      );
    } catch (err) {
      showToast(err.message || 'Could not register vote', 'error');
    } finally {
      voting = false;
    }
  }

  function getDifficultyBadge(diff) {
    if (diff === 'Easy') return 'badge-green';
    if (diff === 'Medium') return 'badge-amber';
    return 'badge-purple';
  }

  $: aggregateRating = recipe.aggregate_rating ?? ((recipe.upvotes_count || 0) - (recipe.downvotes_count || 0));
</script>

<div class="recipe-card" on:click={openDetails} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && openDetails()}>
  <!-- Card Header & Image -->
  <div class="card-media">
    {#if activeImage && !imageError}
      <img
        src={activeImage}
        alt="{recipe.title} (photo {currentImageIndex + 1})"
        class="recipe-img"
        on:error={() => (imageError = true)}
        loading="lazy"
      />
    {:else}
      <div class="fallback-img">
        <span class="fallback-icon">🥘</span>
      </div>
    {/if}

    <!-- Subtle gradient overlays for badge/controls contrast -->
    <div class="media-overlay-top"></div>
    <div class="media-overlay-bottom"></div>

    <!-- Multi-photo controls (counter badge, carousel arrows, pagination dots) -->
    {#if totalImages > 1}
      <div class="photo-count-badge" title="{totalImages} photos available (photo {currentImageIndex + 1} of {totalImages})">
        <span class="photo-icon">📷</span>
        <span>{currentImageIndex + 1}/{totalImages}</span>
      </div>

      <!-- Arrow navigation buttons -->
      <button
        type="button"
        class="gallery-arrow gallery-arrow-prev"
        on:click={prevImage}
        title="Previous photo"
        aria-label="Previous photo"
      >
        <span aria-hidden="true">‹</span>
      </button>

      <button
        type="button"
        class="gallery-arrow gallery-arrow-next"
        on:click={nextImage}
        title="Next photo"
        aria-label="Next photo"
      >
        <span aria-hidden="true">›</span>
      </button>

      <!-- Carousel indicator dots -->
      <div class="gallery-dots" on:click|stopPropagation role="none">
        {#each recipeImages as _, idx}
          <button
            type="button"
            class="gallery-dot {idx === currentImageIndex ? 'active' : ''}"
            on:click={(e) => selectImage(idx, e)}
            title="Switch to photo {idx + 1}"
            aria-label="Switch to photo {idx + 1}"
          ></button>
        {/each}
      </div>
    {/if}

    <!-- Thumbs Up / Thumbs Down / Rating Pill -->
    <div class="vote-widget" on:click|stopPropagation role="none">
      <button
        type="button"
        class="vote-btn upvote-btn {recipe.user_vote === 1 ? 'voted-up' : ''}"
        on:click={handleUpvote}
        title={recipe.user_vote === 1 ? 'Remove upvote' : `Upvote recipe (${recipe.upvotes_count || 0} users)`}
        aria-label="Upvote recipe"
        disabled={voting}
      >
        <span class="thumb-icon">👍</span>
      </button>

      <span
        class="vote-score {aggregateRating > 0 ? 'score-positive' : aggregateRating < 0 ? 'score-negative' : 'score-zero'}"
        title="Aggregate vote rating: {aggregateRating >= 0 ? '+' : ''}{aggregateRating} ({recipe.upvotes_count || 0} upvotes, {recipe.downvotes_count || 0} downvotes)"
      >
        {aggregateRating > 0 ? `+${aggregateRating}` : aggregateRating}
      </span>

      <button
        type="button"
        class="vote-btn downvote-btn {recipe.user_vote === -1 ? 'voted-down' : ''}"
        on:click={handleDownvote}
        title={recipe.user_vote === -1 ? 'Remove downvote' : `Downvote recipe (${recipe.downvotes_count || 0} users)`}
        aria-label="Downvote recipe"
        disabled={voting}
      >
        <span class="thumb-icon">👎</span>
      </button>
    </div>

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

    <!-- Key Metrics including Votes and Duration -->
    <div class="recipe-metrics">
      <div class="metric" title="Total cooking duration">
        <span class="metric-icon">⏱️</span>
        <span class="metric-val">{recipe.total_time_minutes}m</span>
      </div>
      <div class="metric" title="Portions">
        <span class="metric-icon">👥</span>
        <span class="metric-val">{recipe.servings} servings</span>
      </div>
      <div class="metric vote-metric" title="Total users who upvoted ({recipe.upvotes_count || 0}) or downvoted ({recipe.downvotes_count || 0})">
        <span class="metric-icon">⭐</span>
        <span class="metric-val">{aggregateRating >= 0 ? `+${aggregateRating}` : aggregateRating}</span>
        <span class="vote-counts-sub">({recipe.upvotes_count || 0}👍 / {recipe.downvotes_count || 0}👎)</span>
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
    height: 260px;
    background-color: var(--bg-subtle);
    overflow: hidden;
  }

  .recipe-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    display: block;
  }

  .recipe-card:hover .recipe-img {
    transform: scale(1.04);
  }

  .media-overlay-top {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 52px;
    background: linear-gradient(180deg, rgba(0, 0, 0, 0.28) 0%, rgba(0, 0, 0, 0) 100%);
    pointer-events: none;
    z-index: 1;
  }

  .media-overlay-bottom {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 56px;
    background: linear-gradient(0deg, rgba(0, 0, 0, 0.35) 0%, rgba(0, 0, 0, 0) 100%);
    pointer-events: none;
    z-index: 1;
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

  .gallery-arrow {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(0, 0, 0, 0.08);
    color: #1e293b;
    font-size: 1.4rem;
    line-height: 1;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.18);
    z-index: 4;
    opacity: 0;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    user-select: none;
    padding: 0;
  }

  .gallery-arrow-prev {
    left: 0.65rem;
  }

  .gallery-arrow-next {
    right: 0.65rem;
  }

  .recipe-card:hover .gallery-arrow,
  .gallery-arrow:focus {
    opacity: 1;
  }

  .gallery-arrow:hover {
    background: #ffffff;
    transform: translateY(-50%) scale(1.15);
    box-shadow: 0 6px 14px rgba(0, 0, 0, 0.25);
    color: var(--primary);
  }

  .gallery-dots {
    position: absolute;
    bottom: 0.75rem;
    right: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.3rem;
    z-index: 3;
    padding: 0.25rem 0.5rem;
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(6px);
    border-radius: 9999px;
    border: 1px solid rgba(255, 255, 255, 0.2);
  }

  .gallery-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.5);
    border: none;
    padding: 0;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .gallery-dot:hover {
    background: rgba(255, 255, 255, 0.9);
    transform: scale(1.2);
  }

  .gallery-dot.active {
    width: 14px;
    border-radius: 9999px;
    background: #ffffff;
    box-shadow: 0 0 4px rgba(255, 255, 255, 0.8);
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

  /* Floating Voting Widget */
  .vote-widget {
    position: absolute;
    top: 0.75rem;
    right: 0.75rem;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 9999px;
    display: flex;
    align-items: center;
    gap: 0.2rem;
    padding: 0.2rem 0.35rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 5;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }

  .vote-widget:hover {
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
  }

  .vote-btn {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 50%;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 0.95rem;
    transition: all 0.15s ease;
    padding: 0;
  }

  .vote-btn:hover:not(:disabled) {
    transform: scale(1.18);
    background: rgba(0, 0, 0, 0.06);
  }

  .upvote-btn.voted-up {
    background: #dcfce7;
    border-color: #86efac;
    box-shadow: 0 0 6px rgba(34, 197, 94, 0.4);
    transform: scale(1.08);
  }

  .downvote-btn.voted-down {
    background: #fee2e2;
    border-color: #fca5a5;
    box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
    transform: scale(1.08);
  }

  .vote-score {
    font-size: 0.8rem;
    font-weight: 700;
    min-width: 26px;
    text-align: center;
    padding: 0 0.15rem;
    font-variant-numeric: tabular-nums;
  }

  .score-positive {
    color: #15803d;
  }

  .score-negative {
    color: #b91c1c;
  }

  .score-zero {
    color: #64748b;
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
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .recipe-metrics {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    padding-top: 0.85rem;
    border-top: 1px solid var(--border-subtle);
    margin-top: auto;
    font-size: 0.8rem;
    color: var(--text-muted);
    flex-wrap: wrap;
  }

  .metric {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  .vote-metric {
    margin-left: auto;
  }

  .metric-val {
    font-weight: 600;
    color: var(--text-main);
  }

  .vote-counts-sub {
    font-size: 0.72rem;
    color: var(--text-light);
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

