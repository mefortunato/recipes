<script>
  import {
    isFormModalOpen,
    editingRecipe,
    showToast,
    currentUser,
    isAuthModalOpen
  } from '../stores';

  function openCreate() {
    if (!$currentUser) {
      isAuthModalOpen.set(true);
      return;
    }
    if (!$currentUser.can_edit) {
      showToast('Your account is in Viewer mode. Only authorized editors can add recipes.', 'error');
      return;
    }
    editingRecipe.set(null);
    isFormModalOpen.set(true);
  }
</script>

<div class="empty-state animate-fade-in">
  <div class="empty-illustration">🍲</div>
  <h3 class="empty-title">No Recipes Found</h3>
  <p class="empty-sub">
    We couldn't find any recipes matching your current filters, or your recipe book is waiting for its first dish.
  </p>
  <div class="empty-actions">
    {#if $currentUser?.can_edit}
      <button class="btn btn-primary" on:click={openCreate}>
        + Create First Recipe
      </button>
    {:else if !$currentUser}
      <button class="btn btn-primary" on:click={() => isAuthModalOpen.set(true)}>
        🔐 Sign In as Chef to Add Recipes
      </button>
    {:else}
      <p class="viewer-empty-msg">
        👁️ You are viewing in read-only mode. An authorized chef can add recipes.
      </p>
    {/if}
  </div>
</div>

<style>
  .empty-state {
    background: var(--bg-surface);
    border: 2px dashed var(--border-color);
    border-radius: var(--radius-xl);
    padding: 4rem 2rem;
    text-align: center;
    max-width: 600px;
    margin: 3rem auto;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .empty-illustration {
    font-size: 4.5rem;
    margin-bottom: 1rem;
    line-height: 1;
  }

  .empty-title {
    font-family: var(--font-serif);
    font-size: 1.6rem;
    color: var(--text-main);
    margin-bottom: 0.5rem;
  }

  .empty-sub {
    font-size: 0.95rem;
    color: var(--text-muted);
    line-height: 1.5;
    margin-bottom: 1.75rem;
    max-width: 440px;
  }

  .empty-actions {
    display: flex;
    gap: 0.85rem;
    flex-wrap: wrap;
    justify-content: center;
    align-items: center;
  }

  .viewer-empty-msg {
    font-size: 0.88rem;
    color: #94a3b8;
    background: rgba(148, 163, 184, 0.1);
    padding: 0.6rem 1.25rem;
    border-radius: 9999px;
  }
</style>
