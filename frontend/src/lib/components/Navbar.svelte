<script>
  import {
    filters,
    loadRecipes,
    isFormModalOpen,
    editingRecipe,
    systemHealth,
    showToast,
    loadMetadata,
    currentUser,
    isAuthModalOpen,
    isAdminModalOpen,
    handleLogout,
    authLoading
  } from '../stores';
  import { api } from '../api';

  let searchTimeout;
  let seeding = false;
  let isUserMenuOpen = false;

  function openAdminPanel() {
    closeUserMenu();
    isAdminModalOpen.set(true);
  }

  function handleSearchInput(e) {
    const val = e.target.value;
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      filters.update((f) => ({ ...f, search: val }));
      loadRecipes();
    }, 300);
  }

  function openCreateModal() {
    if (!$currentUser) {
      showToast('Please sign in as an authorized editor to create recipes.', 'info');
      isAuthModalOpen.set(true);
      return;
    }
    if (!$currentUser.can_edit) {
      showToast('Your account is in Viewer mode. Only authorized editors can create recipes.', 'error');
      return;
    }
    editingRecipe.set(null);
    isFormModalOpen.set(true);
  }

  async function handleSeed() {
    if (!$currentUser) {
      showToast('Please sign in as an authorized editor to seed recipes.', 'info');
      isAuthModalOpen.set(true);
      return;
    }
    if (!$currentUser.can_edit) {
      showToast('Forbidden: Only authorized editors can seed sample recipes.', 'error');
      return;
    }
    if (seeding) return;
    seeding = true;
    try {
      const res = await api.seedRecipes(true);
      showToast(res.message || 'Recipes seeded successfully!', 'success');
      await Promise.all([loadRecipes(), loadMetadata()]);
    } catch (err) {
      showToast(err.message || 'Failed to seed sample recipes', 'error');
    } finally {
      seeding = false;
    }
  }

  function toggleUserMenu() {
    isUserMenuOpen = !isUserMenuOpen;
  }

  function closeUserMenu() {
    isUserMenuOpen = false;
  }

  async function onLogout() {
    closeUserMenu();
    await handleLogout();
  }

  function openAuth() {
    closeUserMenu();
    isAuthModalOpen.set(true);
  }
</script>

<svelte:window on:click={() => (isUserMenuOpen = false)} />

<header class="navbar">
  <div class="navbar-container">
    <!-- Brand Logo -->
    <div class="brand">
      <div class="brand-icon">🍳</div>
      <div class="brand-text">
        <h1 class="brand-title">Gourmet Vault</h1>
        <span class="brand-subtitle">Recipe Book & Kitchen Companion</span>
      </div>
    </div>

    <!-- Live Search -->
    <div class="search-box">
      <span class="search-icon">🔍</span>
      <input
        type="text"
        placeholder="Search recipes, ingredients, cuisines..."
        class="search-input"
        on:input={handleSearchInput}
      />
    </div>

    <!-- Actions & Health -->
    <div class="actions">
      <!-- Cloud Native Health Indicator -->
      <div class="health-indicator" title="Cloud-Native System Health">
        <span
          class="status-dot {$systemHealth.status === 'online' ? 'status-online' : 'status-offline'}"
        ></span>
        <span class="health-text">
          {$systemHealth.status === 'online'
            ? `API Ready (${$systemHealth.latency_ms}ms)`
            : 'Connecting...'}
        </span>
      </div>

      <!-- Seed Sample Recipes -->
      {#if $currentUser?.can_edit}
        <button
          class="btn btn-secondary btn-sm"
          on:click={handleSeed}
          disabled={seeding}
          title="Load curated chef recipes"
        >
          <span>{seeding ? '🌱 Seeding...' : '🌱 Seed Recipes'}</span>
        </button>
      {/if}

      <!-- Admin Panel Button (Privileged Users Only) -->
      {#if $currentUser?.is_admin || $currentUser?.role === 'admin'}
        <button
          class="btn btn-admin btn-sm"
          on:click={openAdminPanel}
          title="Open Access & Permissions Admin Panel"
        >
          <span>🛡️</span>
          <span>Admin Panel</span>
        </button>
      {/if}

      <!-- Add Recipe Button -->
      {#if $currentUser?.can_edit}
        <button
          class="btn btn-primary"
          on:click={openCreateModal}
          title="Create a new recipe"
        >
          <span style="font-size: 1.1rem; line-height: 1;">+</span>
          <span>Add Recipe</span>
        </button>
      {/if}

      <!-- User Account & Auth Section -->
      {#if $currentUser}
        <div class="user-menu-wrapper" on:click|stopPropagation on:keydown|stopPropagation role="none">
          <button class="user-pill-btn" on:click={toggleUserMenu} aria-label="User Account Menu">
            {#if $currentUser.picture}
              <img src={$currentUser.picture} alt={$currentUser.name} class="user-avatar-img" />
            {:else}
              <div class="user-avatar-placeholder">
                {$currentUser.name ? $currentUser.name.charAt(0).toUpperCase() : '👤'}
              </div>
            {/if}
            <span class="user-pill-name">{$currentUser.name.split(' ')[0]}</span>
            <span class="role-badge {$currentUser.role === 'admin' || $currentUser.is_admin ? 'role-admin' : $currentUser.can_edit ? 'role-editor' : 'role-viewer'}">
              {$currentUser.role === 'admin' || $currentUser.is_admin ? '👑 Admin' : $currentUser.can_edit ? '🍳 Chef' : '👁️ Viewer'}
            </span>
            <span class="caret">▾</span>
          </button>

          {#if isUserMenuOpen}
            <div class="user-dropdown-menu animate-fade-in">
              <div class="menu-user-info">
                <span class="menu-user-name">{$currentUser.name}</span>
                <span class="menu-user-email">{$currentUser.email}</span>
                <div class="menu-role-status">
                  <span class="status-indicator-dot {$currentUser.role === 'admin' || $currentUser.is_admin ? 'dot-admin' : $currentUser.can_edit ? 'dot-editor' : 'dot-viewer'}"></span>
                  <span class="status-indicator-label">
                    {$currentUser.role === 'admin' || $currentUser.is_admin ? 'Privileged Administrator' : $currentUser.can_edit ? 'Authorized Recipe Editor' : 'Read-Only Viewer Access'}
                  </span>
                </div>
              </div>

              <div class="menu-divider"></div>

              {#if $currentUser.role === 'admin' || $currentUser.is_admin}
                <button class="menu-item menu-item-admin" on:click={openAdminPanel}>
                  <span>🛡️</span>
                  <span>User Permissions Admin</span>
                </button>
              {/if}

              <button class="menu-item" on:click={openAuth}>
                <span>🔄</span>
                <span>Switch / Sign in with Google</span>
              </button>

              <button class="menu-item menu-item-logout" on:click={onLogout}>
                <span>🚪</span>
                <span>Sign Out</span>
              </button>
            </div>
          {/if}
        </div>
      {:else if !$authLoading}
        <button class="btn btn-google" on:click={() => isAuthModalOpen.set(true)}>
          <svg width="18" height="18" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
          </svg>
          <span>Sign In</span>
        </button>
      {/if}
    </div>
  </div>
</header>

<style>
  .navbar {
    background-color: var(--bg-surface);
    border-bottom: 1px solid var(--border-color);
    position: sticky;
    top: 0;
    z-index: 40;
    box-shadow: var(--shadow-sm);
  }

  .navbar-container {
    max-width: 1380px;
    margin: 0 auto;
    padding: 0.85rem 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.5rem;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    text-decoration: none;
    cursor: default;
  }

  .brand-icon {
    font-size: 2rem;
    background: var(--primary-light);
    border-radius: var(--radius-md);
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .brand-text {
    display: flex;
    flex-direction: column;
  }

  .brand-title {
    font-family: var(--font-serif);
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text-main);
    letter-spacing: -0.02em;
    line-height: 1.1;
  }

  .brand-subtitle {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 500;
  }

  .search-box {
    flex: 1;
    max-width: 460px;
    position: relative;
    display: flex;
    align-items: center;
  }

  .search-icon {
    position: absolute;
    left: 0.85rem;
    font-size: 0.9rem;
    color: var(--text-light);
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    padding: 0.6rem 1rem 0.6rem 2.4rem;
    border-radius: 9999px;
    border: 1px solid var(--border-color);
    background-color: var(--bg-subtle);
    font-family: var(--font-sans);
    font-size: 0.9rem;
    outline: none;
    transition: all 0.2s ease;
  }

  .search-input:focus {
    background-color: var(--bg-surface);
    border-color: var(--primary);
    box-shadow: 0 0 0 3px var(--primary-glow);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 0.85rem;
  }

  .health-indicator {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    background: var(--bg-subtle);
    padding: 0.35rem 0.65rem;
    border-radius: 9999px;
    border: 1px solid var(--border-subtle);
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .status-online {
    background-color: #22c55e;
    box-shadow: 0 0 6px #22c55e;
  }

  .status-offline {
    background-color: #f97316;
    box-shadow: 0 0 6px #f97316;
  }

  .health-text {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
  }

  /* Google Sign-in button */
  .btn-google {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 9999px;
    padding: 0.45rem 0.95rem;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    transition: all 0.2s ease;
  }

  .btn-google:hover {
    background: #f8fafc;
    border-color: #94a3b8;
    transform: translateY(-1px);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  }

  /* User Menu Pill */
  .user-menu-wrapper {
    position: relative;
  }

  .user-pill-btn {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    padding: 0.3rem 0.65rem 0.3rem 0.35rem;
    border-radius: 9999px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .user-pill-btn:hover {
    background: var(--bg-surface);
    border-color: var(--primary);
  }

  .user-avatar-img {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    object-fit: cover;
  }

  .user-avatar-placeholder {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #ea580c;
    color: white;
    font-size: 0.8rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .user-pill-name {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-main);
  }

  .role-badge {
    font-size: 0.68rem;
    font-weight: 700;
    padding: 0.15rem 0.45rem;
    border-radius: 9999px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .role-admin {
    background: rgba(147, 51, 234, 0.18);
    color: #a855f7;
    border: 1px solid rgba(168, 85, 247, 0.4);
  }

  .role-editor {
    background: rgba(16, 185, 129, 0.15);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.3);
  }

  .role-viewer {
    background: rgba(148, 163, 184, 0.15);
    color: #94a3b8;
    border: 1px solid rgba(148, 163, 184, 0.3);
  }

  .caret {
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  /* Admin button in actions bar */
  .btn-admin {
    background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
    color: #ffffff;
    box-shadow: 0 2px 6px rgba(124, 58, 237, 0.35);
    border: 1px solid rgba(216, 180, 254, 0.3);
  }

  .btn-admin:hover {
    background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(124, 58, 237, 0.45);
  }

  /* Dropdown Menu */
  .user-dropdown-menu {
    position: absolute;
    top: calc(100% + 0.5rem);
    right: 0;
    width: 260px;
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 0.85rem;
    box-shadow: 0 15px 30px rgba(0, 0, 0, 0.4);
    padding: 0.75rem 0;
    z-index: 50;
  }

  .menu-user-info {
    padding: 0.5rem 1rem 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .menu-user-name {
    font-size: 0.92rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .menu-user-email {
    font-size: 0.75rem;
    color: #94a3b8;
    word-break: break-all;
  }

  .menu-role-status {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-top: 0.4rem;
    font-size: 0.72rem;
    color: #cbd5e1;
  }

  .status-indicator-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  .dot-admin {
    background: #a855f7;
    box-shadow: 0 0 6px #a855f7;
  }

  .dot-editor {
    background: #10b981;
    box-shadow: 0 0 6px #10b981;
  }

  .dot-viewer {
    background: #94a3b8;
  }

  .menu-divider {
    height: 1px;
    background: rgba(255, 255, 255, 0.08);
    margin: 0.35rem 0;
  }

  .menu-item {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    width: 100%;
    padding: 0.6rem 1rem;
    background: transparent;
    border: none;
    color: #e2e8f0;
    font-size: 0.82rem;
    text-align: left;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .menu-item:hover {
    background: rgba(255, 255, 255, 0.08);
  }

  .menu-item-admin {
    color: #c084fc;
    font-weight: 600;
  }

  .menu-item-admin:hover {
    background: rgba(147, 51, 234, 0.2);
    color: #f3e8ff;
  }

  .menu-item-logout {
    color: #f87171;
  }

  .menu-item-logout:hover {
    background: rgba(239, 68, 68, 0.15);
  }

  @media (max-width: 900px) {
    .navbar-container {
      flex-wrap: wrap;
    }
    .search-box {
      order: 3;
      max-width: 100%;
      flex-basis: 100%;
    }
  }
</style>
