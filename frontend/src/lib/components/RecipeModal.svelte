<script>
  import {
    activeRecipe,
    isViewModalOpen,
    isFormModalOpen,
    editingRecipe,
    loadRecipes,
    showToast,
    currentUser,
    isAuthModalOpen,
    updateRecipeInStore
  } from '../stores';
  import { api } from '../api';

  let currentServings = 4;
  let scaledIngredients = [];
  let checkedIngredients = new Set();
  let checkedSteps = new Set();
  let scaling = false;
  let deleting = false;
  let voting = false;

  $: aggregateRating = $activeRecipe
    ? ($activeRecipe.aggregate_rating ?? (($activeRecipe.upvotes_count || 0) - ($activeRecipe.downvotes_count || 0)))
    : 0;

  async function handleModalUpvote() {
    if (!$currentUser) {
      showToast('Please sign in to vote on recipes.', 'info');
      isAuthModalOpen.set(true);
      return;
    }
    if (voting || !$activeRecipe) return;
    voting = true;
    try {
      const targetVote = $activeRecipe.user_vote === 1 ? 0 : 1;
      const updated = await api.voteRecipe($activeRecipe.id, targetVote);
      activeRecipe.set(updated);
      updateRecipeInStore(updated);
      showToast(targetVote === 1 ? 'Upvoted recipe! 👍' : 'Upvote removed', 'info', 1800);
    } catch (err) {
      showToast(err.message || 'Could not register vote', 'error');
    } finally {
      voting = false;
    }
  }

  async function handleModalDownvote() {
    if (!$currentUser) {
      showToast('Please sign in to vote on recipes.', 'info');
      isAuthModalOpen.set(true);
      return;
    }
    if (voting || !$activeRecipe) return;
    voting = true;
    try {
      const targetVote = $activeRecipe.user_vote === -1 ? 0 : -1;
      const updated = await api.voteRecipe($activeRecipe.id, targetVote);
      activeRecipe.set(updated);
      updateRecipeInStore(updated);
      showToast(targetVote === -1 ? 'Downvoted recipe 👎' : 'Downvote removed', 'info', 1800);
    } catch (err) {
      showToast(err.message || 'Could not register vote', 'error');
    } finally {
      voting = false;
    }
  }

  // Multiple Images Gallery state
  let activeImageIndex = 0;
  let recipeImages = [];

  $: if ($activeRecipe) {
    currentServings = $activeRecipe.servings || 4;
    scaledIngredients = ($activeRecipe.ingredients || []).map((ing) => ({
      ...ing,
      scaled_amount: ing.amount,
    }));
    checkedIngredients = new Set();
    checkedSteps = new Set();

    if ($activeRecipe.images && $activeRecipe.images.length > 0) {
      recipeImages = $activeRecipe.images;
    } else if ($activeRecipe.image_url) {
      recipeImages = [$activeRecipe.image_url];
    } else {
      recipeImages = [];
    }
    activeImageIndex = 0;
  }

  function closeModal() {
    isViewModalOpen.set(false);
    activeRecipe.set(null);
  }

  function nextImage(e) {
    if (e) e.stopPropagation();
    if (recipeImages.length <= 1) return;
    activeImageIndex = (activeImageIndex + 1) % recipeImages.length;
  }

  function prevImage(e) {
    if (e) e.stopPropagation();
    if (recipeImages.length <= 1) return;
    activeImageIndex = (activeImageIndex - 1 + recipeImages.length) % recipeImages.length;
  }

  function setImage(index, e) {
    if (e) e.stopPropagation();
    activeImageIndex = index;
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') closeModal();
    if (recipeImages.length > 1) {
      if (e.key === 'ArrowLeft') prevImage();
      if (e.key === 'ArrowRight') nextImage();
    }
  }

  async function adjustServings(delta) {
    const newServings = Math.max(1, currentServings + delta);
    if (newServings === currentServings || !$activeRecipe) return;

    currentServings = newServings;
    scaling = true;
    try {
      const res = await api.scaleRecipe($activeRecipe.id, newServings);
      scaledIngredients = res.ingredients;
    } catch (err) {
      // Fallback to client-side calculation if offline
      const ratio = newServings / ($activeRecipe.servings || 1);
      scaledIngredients = ($activeRecipe.ingredients || []).map((ing) => ({
        ...ing,
        scaled_amount: Math.round(ing.amount * ratio * 100) / 100,
      }));
    } finally {
      scaling = false;
    }
  }

  function toggleIngredient(index) {
    const next = new Set(checkedIngredients);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    checkedIngredients = next;
  }

  function toggleStep(stepNumber) {
    const next = new Set(checkedSteps);
    if (next.has(stepNumber)) {
      next.delete(stepNumber);
    } else {
      next.add(stepNumber);
    }
    checkedSteps = next;
  }

  function openEdit() {
    editingRecipe.set($activeRecipe);
    isViewModalOpen.set(false);
    isFormModalOpen.set(true);
  }

  async function handleDelete() {
    if (!confirm(`Are you sure you want to delete "${$activeRecipe.title}"?`)) return;
    deleting = true;
    try {
      await api.deleteRecipe($activeRecipe.id);
      showToast('Recipe deleted successfully', 'success');
      closeModal();
      loadRecipes();
    } catch (err) {
      showToast(err.message || 'Failed to delete recipe', 'error');
    } finally {
      deleting = false;
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if $isViewModalOpen && $activeRecipe}
  <div
    class="modal-backdrop"
    on:click={closeModal}
    on:keydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <div
      class="modal-card animate-fade-in"
      on:click|stopPropagation
      on:keydown|stopPropagation
      role="document"
    >
      <!-- Close Button -->
      <button class="close-btn" on:click={closeModal} aria-label="Close modal">✕</button>

      <!-- Hero Header Banner / Gallery -->
      <div class="modal-hero">
        {#if recipeImages.length > 0}
          <img
            src={recipeImages[activeImageIndex]}
            alt="{$activeRecipe.title} (photo {activeImageIndex + 1} of {recipeImages.length})"
            class="hero-image"
          />

          {#if recipeImages.length > 1}
            <!-- Image Navigation Buttons -->
            <button
              type="button"
              class="hero-nav-btn prev-btn"
              on:click={prevImage}
              aria-label="Previous image"
              title="Previous photo (Left arrow)"
            >
              <span aria-hidden="true">‹</span>
            </button>
            <button
              type="button"
              class="hero-nav-btn next-btn"
              on:click={nextImage}
              aria-label="Next image"
              title="Next photo (Right arrow)"
            >
              <span aria-hidden="true">›</span>
            </button>

            <!-- Photo Counter Pill -->
            <div class="hero-counter">
              <span>📷 {activeImageIndex + 1} / {recipeImages.length}</span>
            </div>

            <!-- In-Hero Indicator Dots matching card scrolling gallery -->
            <div class="hero-dots" on:click|stopPropagation role="none">
              {#each recipeImages as _, idx}
                <button
                  type="button"
                  class="hero-dot {idx === activeImageIndex ? 'active' : ''}"
                  on:click={(e) => setImage(idx, e)}
                  title="Switch to photo {idx + 1}"
                  aria-label="Switch to photo {idx + 1}"
                ></button>
              {/each}
            </div>
          {/if}
        {:else}
          <div class="hero-placeholder">🍳</div>
        {/if}

        <div class="hero-overlay">
          <div class="hero-badges">
            <span class="badge badge-amber">{$activeRecipe.cuisine}</span>
            <span class="badge badge-green">{$activeRecipe.difficulty}</span>
            <span class="badge badge-blue">{$activeRecipe.category}</span>
          </div>
          <h2 class="hero-title">{$activeRecipe.title}</h2>
        </div>
      </div>

      <!-- Thumbnail Strip if multiple images -->
      {#if recipeImages.length > 1}
        <div class="thumbnails-strip">
          <span class="thumbnails-label">Photos ({recipeImages.length}):</span>
          <div class="thumbnails-scroll">
            {#each recipeImages as imgUrl, idx}
              <button
                type="button"
                class="thumb-btn {idx === activeImageIndex ? 'active-thumb' : ''}"
                on:click={(e) => setImage(idx, e)}
                title="View photo {idx + 1}"
              >
                <img src={imgUrl} alt="Thumbnail {idx + 1}" class="thumb-img" />
                <span class="thumb-index">{idx + 1}</span>
              </button>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Modal Content Body -->
      <div class="modal-body">
        <p class="recipe-description">{$activeRecipe.description}</p>

        <!-- Stats Bar -->
        <div class="stats-grid">
          <div class="stat-box">
            <span class="stat-label">Prep Time</span>
            <span class="stat-value">⏱️ {$activeRecipe.prep_time_minutes} min</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">Cook Time</span>
            <span class="stat-value">🔥 {$activeRecipe.cook_time_minutes} min</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">Total Time</span>
            <span class="stat-value">⏳ {$activeRecipe.total_time_minutes} min</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">Base Servings</span>
            <span class="stat-value">🍽️ {$activeRecipe.servings}</span>
          </div>
        </div>

        <!-- Voting & Rating Section Card -->
        <div class="vote-section-card">
          <div class="vote-section-left">
            <div class="vote-score-pill">
              <span class="rating-icon">⭐</span>
              <span class="rating-val {aggregateRating > 0 ? 'score-positive' : aggregateRating < 0 ? 'score-negative' : 'score-zero'}">
                {aggregateRating > 0 ? `+${aggregateRating}` : aggregateRating}
              </span>
              <span class="rating-label">Rating</span>
            </div>
            <div class="vote-breakdown">
              <span class="vote-stat-item" title="Users who upvoted">
                <strong>{$activeRecipe.upvotes_count || 0}</strong> upvotes
              </span>
              <span class="vote-stat-sep">•</span>
              <span class="vote-stat-item" title="Users who downvoted">
                <strong>{$activeRecipe.downvotes_count || 0}</strong> downvotes
              </span>
            </div>
          </div>

          <div class="vote-actions">
            <button
              type="button"
              class="modal-vote-btn upvote-btn {$activeRecipe.user_vote === 1 ? 'voted-up' : ''}"
              on:click={handleModalUpvote}
              disabled={voting}
              title={$activeRecipe.user_vote === 1 ? 'Remove upvote' : 'Upvote this recipe'}
            >
              <span>👍</span>
              <span>{$activeRecipe.user_vote === 1 ? 'Upvoted' : 'Upvote'}</span>
            </button>
            <button
              type="button"
              class="modal-vote-btn downvote-btn {$activeRecipe.user_vote === -1 ? 'voted-down' : ''}"
              on:click={handleModalDownvote}
              disabled={voting}
              title={$activeRecipe.user_vote === -1 ? 'Remove downvote' : 'Downvote this recipe'}
            >
              <span>👎</span>
              <span>{$activeRecipe.user_vote === -1 ? 'Downvoted' : 'Downvote'}</span>
            </button>
          </div>
        </div>

        <!-- Serving Size Scaler -->
        <div class="scaler-card">
          <div class="scaler-info">
            <h4 class="scaler-heading">Interactive Serving Scaler</h4>
            <p class="scaler-sub">Ingredient amounts update automatically for your portion size.</p>
          </div>
          <div class="scaler-controls">
            <button
              class="scale-btn"
              on:click={() => adjustServings(-1)}
              disabled={currentServings <= 1 || scaling}
            >-</button>
            <span class="servings-display">{currentServings} servings</span>
            <button
              class="scale-btn"
              on:click={() => adjustServings(1)}
              disabled={currentServings >= 50 || scaling}
            >+</button>
          </div>
        </div>

        <!-- Two Column: Ingredients & Instructions -->
        <div class="recipe-columns">
          <!-- Ingredients Column -->
          <div class="column-ingredients">
            <div class="section-header">
              <h3 class="section-title">Ingredients</h3>
              <span class="section-hint">Check off as you prep</span>
            </div>

            <ul class="ingredients-list">
              {#each scaledIngredients as ing, idx}
                <li>
                  <label class="ingredient-item {checkedIngredients.has(idx) ? 'item-checked' : ''}">
                    <input
                      type="checkbox"
                      checked={checkedIngredients.has(idx)}
                      on:change={() => toggleIngredient(idx)}
                    />
                    <div class="ingredient-details">
                      <span class="ing-amount">{ing.scaled_amount} {ing.unit}</span>
                      <strong class="ing-name">{ing.name}</strong>
                      {#if ing.notes}
                        <span class="ing-notes">({ing.notes})</span>
                      {/if}
                    </div>
                  </label>
                </li>
              {/each}
            </ul>
          </div>

          <!-- Instructions Column -->
          <div class="column-instructions">
            <div class="section-header">
              <h3 class="section-title">Instructions</h3>
              <span class="section-hint">Track your steps</span>
            </div>

            <ol class="instructions-list">
              {#each $activeRecipe.instructions as step}
                <li>
                  <div
                    class="step-item {checkedSteps.has(step.step_number) ? 'step-checked' : ''}"
                    on:click={() => toggleStep(step.step_number)}
                    on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleStep(step.step_number)}
                    role="button"
                    tabindex="0"
                  >
                    <div class="step-badge">{step.step_number}</div>
                    <div class="step-content">
                      <p class="step-text">{step.instruction}</p>
                      {#if step.tip}
                        <div class="step-tip">
                          <span class="tip-icon">💡</span>
                          <span class="tip-text">{step.tip}</span>
                        </div>
                      {/if}
                    </div>
                  </div>
                </li>
              {/each}
            </ol>

            {#if $activeRecipe.notes}
              <div class="chef-notes">
                <strong>Chef's Note:</strong> {$activeRecipe.notes}
              </div>
            {/if}
          </div>
        </div>

        <!-- Tags -->
        {#if $activeRecipe.tags && $activeRecipe.tags.length > 0}
          <div class="modal-tags">
            {#each $activeRecipe.tags as tag}
              <span class="badge badge-gray">#{tag}</span>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Modal Footer Actions -->
      <div class="modal-footer">
        {#if $currentUser?.can_edit}
          <button class="btn btn-danger btn-sm" on:click={handleDelete} disabled={deleting}>
            {deleting ? 'Deleting...' : '🗑️ Delete Recipe'}
          </button>
          <div class="footer-right">
            <button class="btn btn-secondary" on:click={openEdit}>✏️ Edit Recipe</button>
            <button class="btn btn-primary" on:click={closeModal}>Done</button>
          </div>
        {:else}
          <div class="viewer-footer-note">
            <span class="lock-icon">🔒</span>
            <span class="note-text">
              Viewing Mode •
              {#if !$currentUser}
                <button class="btn-sign-in-link" on:click={() => { isAuthModalOpen.set(true); }}>Sign in as Chef</button> to edit
              {:else}
                Only authorized editors can edit or delete this recipe
              {/if}
            </span>
          </div>
          <div class="footer-right">
            <button class="btn btn-primary" on:click={closeModal}>Done</button>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .viewer-footer-note {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.82rem;
    color: #94a3b8;
  }

  .btn-sign-in-link {
    background: transparent;
    border: none;
    color: #38bdf8;
    text-decoration: underline;
    font-weight: 600;
    cursor: pointer;
    padding: 0;
    font-size: inherit;
  }

  .btn-sign-in-link:hover {
    color: #0284c7;
  }

  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(4px);
    z-index: 50;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    overflow-y: auto;
  }

  .modal-card {
    background: var(--bg-surface);
    width: 100%;
    max-width: 900px;
    max-height: 90vh;
    border-radius: var(--radius-xl);
    overflow-y: auto;
    position: relative;
    box-shadow: var(--shadow-xl);
    display: block;
  }

  .close-btn {
    position: absolute;
    top: 1.25rem;
    right: 1.25rem;
    background: rgba(15, 23, 42, 0.72);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 50%;
    width: 38px;
    height: 38px;
    font-size: 1.15rem;
    font-weight: 700;
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    z-index: 25;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    transition: all 0.2s ease;
  }

  .close-btn:hover {
    background: rgba(15, 23, 42, 0.95);
    transform: scale(1.1);
  }

  .modal-hero {
    position: relative;
    width: 100%;
    height: 380px;
    min-height: 380px;
    background: #1c1917;
    overflow: hidden;
    display: block;
  }

  .hero-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
    transition: opacity 0.25s ease;
  }

  .hero-nav-btn {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(6px);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.3);
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.6rem;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    z-index: 15;
    transition: all 0.18s ease;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
  }

  .hero-nav-btn:hover {
    background: rgba(15, 23, 42, 0.9);
    transform: translateY(-50%) scale(1.12);
  }

  .prev-btn {
    left: 1.25rem;
  }

  .next-btn {
    right: 1.25rem;
  }

  .hero-counter {
    position: absolute;
    top: 1.25rem;
    left: 1.25rem;
    background: rgba(15, 23, 42, 0.75);
    backdrop-filter: blur(6px);
    color: #ffffff;
    font-size: 0.8rem;
    font-weight: 700;
    padding: 0.3rem 0.75rem;
    border-radius: 9999px;
    z-index: 15;
    border: 1px solid rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    gap: 0.3rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .hero-dots {
    position: absolute;
    top: 1.25rem;
    right: 4.5rem;
    display: flex;
    align-items: center;
    gap: 0.35rem;
    z-index: 15;
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(6px);
    padding: 0.35rem 0.65rem;
    border-radius: 9999px;
    border: 1px solid rgba(255, 255, 255, 0.2);
  }

  .hero-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.5);
    border: none;
    padding: 0;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .hero-dot:hover {
    background: rgba(255, 255, 255, 0.9);
    transform: scale(1.25);
  }

  .hero-dot.active {
    width: 18px;
    border-radius: 9999px;
    background: #ffffff;
    box-shadow: 0 0 6px rgba(255, 255, 255, 0.9);
  }

  .thumbnails-strip {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.85rem 2rem;
    background: var(--bg-subtle);
    border-bottom: 1px solid var(--border-color);
    overflow-x: auto;
  }

  .thumbnails-label {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    white-space: nowrap;
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  .thumbnails-scroll {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    overflow-x: auto;
    padding: 2px 0;
  }

  .thumb-btn {
    background: #ffffff;
    border: 2px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 3px;
    cursor: pointer;
    width: 84px;
    height: 84px;
    flex-shrink: 0;
    overflow: hidden;
    position: relative;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    opacity: 0.75;
    box-shadow: var(--shadow-sm);
  }

  .thumb-btn:hover {
    opacity: 1;
    transform: translateY(-2px);
    border-color: var(--primary);
    box-shadow: var(--shadow-md);
  }

  .thumb-btn.active-thumb {
    border-color: var(--primary);
    opacity: 1;
    box-shadow: 0 0 0 3px var(--primary-glow);
    transform: scale(1.05);
  }

  .thumb-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: calc(var(--radius-md) - 4px);
    display: block;
  }

  .thumb-index {
    position: absolute;
    bottom: 5px;
    right: 5px;
    background: rgba(15, 23, 42, 0.75);
    backdrop-filter: blur(4px);
    color: #ffffff;
    font-size: 0.68rem;
    font-weight: 700;
    padding: 0.1rem 0.35rem;
    border-radius: 9999px;
    pointer-events: none;
  }

  .hero-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 5rem;
    background: linear-gradient(135deg, #e6f4f6 0%, #c5e8eb 100%);
  }

  .hero-overlay {
    position: absolute;
    bottom: 0;
    inset-inline: 0;
    padding: 3rem 2rem 1.5rem;
    background: linear-gradient(to top, rgba(0, 0, 0, 0.88) 0%, rgba(0, 0, 0, 0.35) 65%, rgba(0, 0, 0, 0) 100%);
    color: white;
  }

  .hero-badges {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.6rem;
  }

  .hero-title {
    font-family: var(--font-serif);
    font-size: 2.15rem;
    font-weight: 700;
    line-height: 1.2;
    color: #ffffff;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
  }

  .modal-body {
    padding: 1.75rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .recipe-description {
    font-size: 1.05rem;
    color: var(--text-muted);
    line-height: 1.6;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 0.75rem;
  }

  .stat-box {
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    padding: 0.75rem;
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .stat-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .stat-value {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text-main);
    margin-top: 0.2rem;
  }

  /* Voting & Rating Section in Modal */
  .vote-section-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 0.9rem 1.25rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
    box-shadow: var(--shadow-sm);
  }

  .vote-section-left {
    display: flex;
    align-items: center;
    gap: 1.1rem;
    flex-wrap: wrap;
  }

  .vote-score-pill {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    background: var(--bg-subtle);
    padding: 0.35rem 0.8rem;
    border-radius: 9999px;
    border: 1px solid var(--border-subtle);
  }

  .rating-icon {
    font-size: 1rem;
  }

  .rating-val {
    font-size: 1.15rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }

  .rating-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
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

  .vote-breakdown {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .vote-stat-item strong {
    color: var(--text-main);
  }

  .vote-stat-sep {
    color: var(--border-color);
  }

  .vote-actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .modal-vote-btn {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.45rem 0.95rem;
    border-radius: 9999px;
    border: 1px solid var(--border-color);
    background: var(--bg-subtle);
    color: var(--text-main);
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .modal-vote-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: var(--shadow-sm);
  }

  .modal-vote-btn.upvote-btn:hover:not(:disabled) {
    background: #ecfdf5;
    border-color: #86efac;
    color: #065f46;
  }

  .modal-vote-btn.upvote-btn.voted-up {
    background: #dcfce7;
    border-color: #22c55e;
    color: #15803d;
    box-shadow: 0 0 8px rgba(34, 197, 94, 0.35);
  }

  .modal-vote-btn.downvote-btn:hover:not(:disabled) {
    background: #fef2f2;
    border-color: #fca5a5;
    color: #991b1b;
  }

  .modal-vote-btn.downvote-btn.voted-down {
    background: #fee2e2;
    border-color: #ef4444;
    color: #b91c1c;
    box-shadow: 0 0 8px rgba(239, 68, 68, 0.35);
  }

  .scaler-card {
    background: var(--primary-light);
    border: 1px solid #c5e8eb;
    border-radius: var(--radius-md);
    padding: 1rem 1.25rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .scaler-heading {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--primary);
  }

  .scaler-sub {
    font-size: 0.8rem;
    color: #0c5867;
  }

  .scaler-controls {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .scale-btn {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    border: 1px solid var(--primary);
    background: white;
    color: var(--primary);
    font-size: 1.25rem;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease;
  }

  .scale-btn:hover:not(:disabled) {
    background: var(--primary);
    color: white;
  }

  .scale-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .servings-display {
    font-weight: 700;
    font-size: 1rem;
    color: var(--primary);
    min-width: 90px;
    text-align: center;
  }

  .recipe-columns {
    display: grid;
    grid-template-columns: 1fr 1.3fr;
    gap: 2rem;
  }

  .section-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 0.85rem;
    border-bottom: 2px solid var(--border-subtle);
    padding-bottom: 0.4rem;
  }

  .section-title {
    font-family: var(--font-serif);
    font-size: 1.3rem;
    color: var(--text-main);
  }

  .section-hint {
    font-size: 0.75rem;
    color: var(--text-light);
  }

  .ingredients-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .ingredient-item {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.65rem;
    border-radius: var(--radius-sm);
    background: var(--bg-subtle);
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .ingredient-item:hover {
    background: #ece8df;
  }

  .ingredient-item.item-checked {
    opacity: 0.5;
    text-decoration: line-through;
  }

  .ingredient-details {
    display: flex;
    gap: 0.35rem;
    font-size: 0.88rem;
    flex-wrap: wrap;
  }

  .ing-amount {
    font-weight: 700;
    color: var(--primary);
  }

  .ing-name {
    color: var(--text-main);
  }

  .ing-notes {
    color: var(--text-muted);
    font-style: italic;
  }

  .instructions-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 1.1rem;
  }

  .step-item {
    display: flex;
    gap: 1rem;
    cursor: pointer;
  }

  .step-badge {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--primary);
    color: white;
    font-size: 0.82rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .step-checked .step-badge {
    background: #16a34a;
  }

  .step-checked .step-text {
    opacity: 0.5;
    text-decoration: line-through;
  }

  .step-content {
    flex: 1;
  }

  .step-text {
    font-size: 0.92rem;
    line-height: 1.55;
    color: var(--text-main);
  }

  .step-tip {
    margin-top: 0.4rem;
    padding: 0.4rem 0.65rem;
    background: #fffbeb;
    border-left: 3px solid #f59e0b;
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    font-size: 0.8rem;
    color: #92400e;
    display: flex;
    gap: 0.4rem;
  }

  .chef-notes {
    margin-top: 1.25rem;
    padding: 0.85rem;
    background: #fdf2f8;
    border: 1px solid #fbcfe8;
    border-radius: var(--radius-md);
    font-size: 0.85rem;
    color: #831843;
  }

  .modal-tags {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
    padding-top: 0.5rem;
    border-top: 1px solid var(--border-subtle);
  }

  .modal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 2rem;
    background: var(--bg-subtle);
    border-top: 1px solid var(--border-color);
  }

  .footer-right {
    display: flex;
    gap: 0.75rem;
  }

  @media (max-width: 768px) {
    .recipe-columns {
      grid-template-columns: 1fr;
    }
    .modal-hero {
      height: 260px;
    }
    .hero-title {
      font-size: 1.45rem;
    }
    .thumb-btn {
      width: 70px;
      height: 70px;
    }
    .hero-dots {
      display: none;
    }
  }
</style>
