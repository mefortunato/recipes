<script>
  import { onMount } from 'svelte';
  import {
    recipes,
    totalRecipes,
    currentPage,
    totalPages,
    loading,
    loadRecipes,
    loadMetadata,
    checkBackendHealth,
    systemHealth,
    initAuth
  } from './lib/stores';

  import Navbar from './lib/components/Navbar.svelte';
  import FilterBar from './lib/components/FilterBar.svelte';
  import RecipeCard from './lib/components/RecipeCard.svelte';
  import RecipeModal from './lib/components/RecipeModal.svelte';
  import RecipeFormModal from './lib/components/RecipeFormModal.svelte';
  import AuthModal from './lib/components/AuthModal.svelte';
  import Toast from './lib/components/Toast.svelte';
  import EmptyState from './lib/components/EmptyState.svelte';

  onMount(() => {
    initAuth();
    checkBackendHealth();
    loadRecipes();
    loadMetadata();

    // Check health every 30s
    const interval = setInterval(checkBackendHealth, 30000);
    return () => clearInterval(interval);
  });

  function goToPage(page) {
    if (page < 1 || page > $totalPages) return;
    currentPage.set(page);
    loadRecipes();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
</script>

<div class="app-container">
  <!-- Top Navigation Header -->
  <Navbar />

  <!-- Main Content Layout -->
  <main class="main-content">
    <!-- Hero Banner / Subtitle -->
    <section class="hero-intro">
      <div class="hero-content">
        <h2 class="hero-heading">Welcome to your personal culinary vault</h2>
        <p class="hero-tagline">
          Store, organize, scale, and cook delicious recipes from around the globe.
        </p>
      </div>
    </section>

    <!-- Filter & Search Controls -->
    <FilterBar />

    <!-- Loading State -->
    {#if $loading}
      <div class="loading-container">
        <div class="loading-spinner"></div>
        <p class="loading-text">Preparing delicious recipes...</p>
      </div>
    {:else if $recipes.length === 0}
      <!-- Empty State -->
      <EmptyState />
    {:else}
      <!-- Recipe Cards Grid -->
      <div class="recipes-grid">
        {#each $recipes as recipe (recipe.id)}
          <RecipeCard {recipe} />
        {/each}
      </div>

      <!-- Pagination Controls -->
      {#if $totalPages > 1}
        <div class="pagination-bar">
          <button
            class="btn btn-secondary btn-sm"
            disabled={$currentPage <= 1}
            on:click={() => goToPage($currentPage - 1)}
          >
            ← Previous
          </button>

          <span class="page-indicator">
            Page {$currentPage} of {$totalPages}
          </span>

          <button
            class="btn btn-secondary btn-sm"
            disabled={$currentPage >= $totalPages}
            on:click={() => goToPage($currentPage + 1)}
          >
            Next →
          </button>
        </div>
      {/if}
    {/if}
  </main>

  <!-- Application Footer -->
  <footer class="app-footer">
    <div class="footer-container">
      <div class="footer-left">
        <strong>Gourmet Vault</strong> • Built with FastAPI, Svelte & MongoDB
      </div>
      <div class="footer-right">
        <span>Docker Managed • Cloud-Native Ready</span>
        <span class="footer-sep">|</span>
        <a href="/docs" target="_blank" rel="noopener noreferrer" class="footer-link">
          OpenAPI /docs
        </a>
      </div>
    </div>
  </footer>

  <!-- Modals & Overlays -->
  <RecipeModal />
  <RecipeFormModal />
  <AuthModal />
  <Toast />
</div>

<style>
  .app-container {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  .main-content {
    flex: 1;
    max-width: 1380px;
    width: 100%;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
  }

  .hero-intro {
    margin-bottom: 2rem;
  }

  .hero-heading {
    font-family: var(--font-serif);
    font-size: 2.25rem;
    font-weight: 700;
    color: var(--text-main);
    letter-spacing: -0.02em;
    margin-bottom: 0.35rem;
  }

  .hero-tagline {
    font-size: 1.05rem;
    color: var(--text-muted);
  }

  .loading-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 6rem 2rem;
    gap: 1.25rem;
  }

  .loading-spinner {
    width: 44px;
    height: 44px;
    border: 4px solid var(--border-color);
    border-top-color: var(--primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .loading-text {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-muted);
  }

  .recipes-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
    gap: 1.75rem;
  }

  .pagination-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1.5rem;
    margin-top: 3rem;
    padding-top: 2rem;
    border-top: 1px solid var(--border-subtle);
  }

  .page-indicator {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-muted);
  }

  .app-footer {
    background-color: var(--bg-surface);
    border-top: 1px solid var(--border-color);
    padding: 1.5rem;
    margin-top: auto;
  }

  .footer-container {
    max-width: 1380px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.82rem;
    color: var(--text-muted);
    flex-wrap: wrap;
    gap: 1rem;
  }

  .footer-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .footer-sep {
    color: var(--border-color);
  }

  .footer-link {
    color: var(--primary);
    text-decoration: none;
    font-weight: 600;
  }

  .footer-link:hover {
    text-decoration: underline;
  }

  @media (max-width: 640px) {
    .hero-heading {
      font-size: 1.75rem;
    }
  }
</style>
