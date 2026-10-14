<script>
  import {
    activeRecipe,
    isViewModalOpen,
    isFormModalOpen,
    editingRecipe,
    loadRecipes,
    showToast,
    currentUser,
    isAuthModalOpen
  } from '../stores';
  import { api } from '../api';

  let currentServings = 4;
  let scaledIngredients = [];
  let checkedIngredients = new Set();
  let checkedSteps = new Set();
  let scaling = false;
  let deleting = false;

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
            alt={$activeRecipe.title}
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
              ‹
            </button>
            <button
              type="button"
              class="hero-nav-btn next-btn"
              on:click={nextImage}
              aria-label="Next image"
              title="Next photo (Right arrow)"
            >
              ›
            </button>

            <!-- Photo Counter Pill -->
            <div class="hero-counter">
              <span>📷 {activeImageIndex + 1} / {recipeImages.length}</span>
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
          {#each recipeImages as imgUrl, idx}
            <button
              type="button"
              class="thumb-btn {idx === activeImageIndex ? 'active-thumb' : ''}"
              on:click={(e) => setImage(idx, e)}
              title="View photo {idx + 1}"
            >
              <img src={imgUrl} alt="Thumbnail {idx + 1}" class="thumb-img" />
            </button>
          {/each}
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
    display: flex;
    flex-direction: column;
  }

  .close-btn {
    position: absolute;
    top: 1rem;
    right: 1rem;
    background: rgba(255, 255, 255, 0.9);
    border: none;
    border-radius: 50%;
    width: 36px;
    height: 36px;
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-main);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    z-index: 10;
    box-shadow: var(--shadow-md);
  }

  .close-btn:hover {
    background: #ffffff;
    transform: scale(1.1);
  }

  .modal-hero {
    position: relative;
    width: 100%;
    height: 280px;
    background: #292524;
    overflow: hidden;
  }

  .hero-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: opacity 0.2s ease;
  }

  .hero-nav-btn {
    position: absolute;
    top: 45%;
    transform: translateY(-50%);
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(4px);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.3);
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    z-index: 15;
    transition: all 0.15s ease;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
  }

  .hero-nav-btn:hover {
    background: rgba(15, 23, 42, 0.85);
    transform: translateY(-50%) scale(1.1);
  }

  .prev-btn {
    left: 1rem;
  }

  .next-btn {
    right: 1rem;
  }

  .hero-counter {
    position: absolute;
    top: 1rem;
    left: 1rem;
    background: rgba(15, 23, 42, 0.7);
    backdrop-filter: blur(4px);
    color: #ffffff;
    font-size: 0.76rem;
    font-weight: 700;
    padding: 0.25rem 0.65rem;
    border-radius: 9999px;
    z-index: 15;
    border: 1px solid rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .thumbnails-strip {
    display: flex;
    gap: 0.6rem;
    padding: 0.75rem 2rem;
    background: var(--bg-subtle);
    border-bottom: 1px solid var(--border-color);
    overflow-x: auto;
    align-items: center;
  }

  .thumb-btn {
    background: none;
    border: 2px solid transparent;
    border-radius: var(--radius-md);
    padding: 2px;
    cursor: pointer;
    width: 56px;
    height: 56px;
    flex-shrink: 0;
    overflow: hidden;
    transition: all 0.2s ease;
    opacity: 0.65;
  }

  .thumb-btn:hover {
    opacity: 1;
    transform: translateY(-2px);
  }

  .thumb-btn.active-thumb {
    border-color: var(--primary);
    opacity: 1;
    box-shadow: 0 0 0 2px var(--primary-glow);
    transform: scale(1.04);
  }

  .thumb-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    border-radius: calc(var(--radius-md) - 3px);
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
    padding: 2rem 2rem 1.25rem;
    background: linear-gradient(to top, rgba(0, 0, 0, 0.85) 0%, rgba(0, 0, 0, 0) 100%);
    color: white;
  }

  .hero-badges {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .hero-title {
    font-family: var(--font-serif);
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.2;
    color: #ffffff;
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
      height: 200px;
    }
    .hero-title {
      font-size: 1.4rem;
    }
  }
</style>
