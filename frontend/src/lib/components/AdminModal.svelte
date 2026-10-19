<script>
  import { onMount } from 'svelte';
  import {
    isAdminModalOpen,
    currentUser,
    showToast,
    loadRecipes,
    loadMetadata
  } from '../stores';
  import { api } from '../api';

  let users = [];
  let loading = false;
  let savingUserId = null;
  let searchQuery = '';
  let selectedRoleFilter = 'All';
  let isProvisionOpen = false;

  // Provisioning form state
  let newEmail = '';
  let newName = '';
  let newRole = 'editor';
  let provisioning = false;

  // Delete confirmation state
  let deletingUserId = null;

  // Metrics
  let metrics = {
    total: 0,
    admin_count: 0,
    editor_count: 0,
    viewer_count: 0,
  };

  // Database Seeding state
  let dbRecipeCount = null;
  let loadingDbStats = false;
  let seeding = false;
  let isSeedConfirmOpen = false;
  let seedVerifyInput = '';

  $: if ($isAdminModalOpen) {
    loadUsers();
    loadDbStats();
  }

  function closeModal() {
    isAdminModalOpen.set(false);
    isProvisionOpen = false;
    isSeedConfirmOpen = false;
    seedVerifyInput = '';
  }

  async function loadDbStats() {
    loadingDbStats = true;
    try {
      const data = await api.getRecipes({ page_size: 1 });
      dbRecipeCount = data.total ?? 0;
    } catch (err) {
      console.warn('Failed to fetch DB recipe count:', err);
    } finally {
      loadingDbStats = false;
    }
  }

  async function handleSeedClick() {
    if (seeding) return;

    // Refresh latest count to guarantee accuracy before proceeding
    try {
      const data = await api.getRecipes({ page_size: 1 });
      dbRecipeCount = data.total ?? 0;
    } catch {
      // fallback to current dbRecipeCount
    }

    if (dbRecipeCount !== null && dbRecipeCount > 0) {
      seedVerifyInput = '';
      isSeedConfirmOpen = true;
    } else {
      await executeSeed(false);
    }
  }

  function closeSeedConfirm() {
    isSeedConfirmOpen = false;
    seedVerifyInput = '';
  }

  async function executeVerifiedSeed() {
    if (seedVerifyInput.trim().toUpperCase() !== 'SEED') {
      showToast('Please type SEED to confirm database seeding.', 'error');
      return;
    }
    await executeSeed(true);
  }

  async function executeSeed(force = false) {
    if (seeding) return;
    seeding = true;
    try {
      const res = await api.seedRecipes(force);
      showToast(res.message || 'Recipes seeded successfully! 🎉', 'success');
      closeSeedConfirm();
      await Promise.all([loadDbStats(), loadRecipes(), loadMetadata()]);
    } catch (err) {
      showToast(err.message || 'Failed to seed sample recipes', 'error');
    } finally {
      seeding = false;
    }
  }

  async function loadUsers() {
    if (loading) return;
    loading = true;
    try {
      const data = await api.getAdminUsers({
        search: searchQuery.trim() || undefined,
        role: selectedRoleFilter !== 'All' ? selectedRoleFilter.toLowerCase() : undefined,
      });
      users = data.users || [];
      metrics = {
        total: data.total || 0,
        admin_count: data.admin_count || 0,
        editor_count: data.editor_count || 0,
        viewer_count: data.viewer_count || 0,
      };
    } catch (err) {
      showToast(err.message || 'Failed to load user permissions', 'error');
    } finally {
      loading = false;
    }
  }

  let searchDebounce;
  function handleSearchInput(e) {
    searchQuery = e.target.value;
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      loadUsers();
    }, 300);
  }

  function clearSearch() {
    searchQuery = '';
    loadUsers();
  }

  function handleFilterTab(tab) {
    selectedRoleFilter = tab;
    loadUsers();
  }

  async function handleRoleChange(user, event) {
    const targetRole = event.target.value;
    if (user.role === targetRole) return;

    savingUserId = user.id;
    try {
      const updated = await api.updateUserPermissions(user.id, { role: targetRole });
      showToast(`Role updated for ${user.email} → ${targetRole.toUpperCase()}`, 'success');

      // Update local state
      users = users.map((u) => (u.id === user.id ? { ...u, ...updated } : u));
      // Re-fetch metrics
      loadUsers();
    } catch (err) {
      showToast(err.message || 'Could not update user role', 'error');
      // Revert select input
      event.target.value = user.role;
    } finally {
      savingUserId = null;
    }
  }

  async function handleToggleEdit(user, e) {
    const canEdit = e.target.checked;
    savingUserId = user.id;
    try {
      const updated = await api.updateUserPermissions(user.id, { can_edit: canEdit });
      showToast(`Recipe edit access ${canEdit ? 'granted to' : 'revoked from'} ${user.email}`, 'info');
      users = users.map((u) => (u.id === user.id ? { ...u, ...updated } : u));
      loadUsers();
    } catch (err) {
      showToast(err.message || 'Could not update recipe editing permission', 'error');
      e.target.checked = !canEdit;
    } finally {
      savingUserId = null;
    }
  }

  async function handleProvision() {
    if (!newEmail || !newEmail.includes('@')) {
      showToast('Please provide a valid email address.', 'error');
      return;
    }
    provisioning = true;
    try {
      const created = await api.provisionUser({
        email: newEmail.trim(),
        name: newName.trim() || undefined,
        role: newRole,
      });
      showToast(`User ${created.email} pre-authorized with role ${created.role.toUpperCase()} 🎉`, 'success');
      newEmail = '';
      newName = '';
      newRole = 'editor';
      isProvisionOpen = false;
      await loadUsers();
    } catch (err) {
      showToast(err.message || 'Failed to pre-authorize user', 'error');
    } finally {
      provisioning = false;
    }
  }

  async function handleDeleteUser(user) {
    if (!confirm(`Are you sure you want to remove user "${user.name || user.email}"?`)) {
      return;
    }
    deletingUserId = user.id;
    try {
      await api.deleteUser(user.id);
      showToast(`User ${user.email} removed successfully.`, 'info');
      users = users.filter((u) => u.id !== user.id);
      loadUsers();
    } catch (err) {
      showToast(err.message || 'Failed to delete user', 'error');
    } finally {
      deletingUserId = null;
    }
  }

  function formatDate(d) {
    if (!d) return 'Never';
    try {
      return new Date(d).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return 'Unknown';
    }
  }
</script>

{#if $isAdminModalOpen}
  <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
  <div
    class="modal-backdrop"
    on:click={closeModal}
    on:keydown={(e) => e.key === 'Escape' && closeModal()}
    role="presentation"
  >
    <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
    <div
      class="admin-card animate-fade-in"
      on:click|stopPropagation
      on:keydown|stopPropagation
      role="dialog"
      aria-modal="true"
      aria-labelledby="admin-title-heading"
      tabindex="-1"
    >
      <!-- Header -->
      <div class="admin-header">
        <div class="header-main">
          <div class="admin-icon-glow">
            <span class="icon">🛡️</span>
          </div>
          <div class="header-text">
            <div class="header-top-row">
              <h2 id="admin-title-heading" class="admin-title">Access & Permissions Admin</h2>
              <span class="badge-env-notice" title="Role-based access control enabled">
                RBAC Active
              </span>
            </div>
            <p class="admin-subtitle">
              Manage authorized kitchen editors, promote administrators, and grant recipe permissions.
            </p>
          </div>
        </div>
        <button class="close-btn" on:click={closeModal} aria-label="Close modal">✕</button>
      </div>

      <!-- Quick Metrics Summary -->
      <div class="metrics-grid">
        <div class="metric-card card-total">
          <div class="metric-info">
            <span class="metric-label">Registered Accounts</span>
            <span class="metric-value">{metrics.total}</span>
          </div>
          <span class="metric-icon">👥</span>
        </div>

        <div class="metric-card card-admin">
          <div class="metric-info">
            <span class="metric-label">Administrators</span>
            <span class="metric-value text-purple">{metrics.admin_count}</span>
          </div>
          <span class="metric-icon">👑</span>
        </div>

        <div class="metric-card card-editor">
          <div class="metric-info">
            <span class="metric-label">Recipe Editors</span>
            <span class="metric-value text-emerald">{metrics.editor_count}</span>
          </div>
          <span class="metric-icon">🍳</span>
        </div>

        <div class="metric-card card-viewer">
          <div class="metric-info">
            <span class="metric-label">Viewers</span>
            <span class="metric-value text-slate">{metrics.viewer_count}</span>
          </div>
          <span class="metric-icon">👁️</span>
        </div>
      </div>

      <!-- Database Status & Seeding Card -->
      <div class="db-seeding-card">
        <div class="db-seeding-info">
          <div class="db-seeding-badge-row">
            <span class="db-icon">🌱</span>
            <span class="db-card-title">Recipe Catalog Database</span>
            <span class="badge-db-count {dbRecipeCount === 0 ? 'badge-db-empty' : 'badge-db-populated'}">
              {loadingDbStats && dbRecipeCount === null
                ? 'Checking...'
                : `${dbRecipeCount ?? 0} ${(dbRecipeCount === 1) ? 'Recipe' : 'Recipes'} in DB`}
            </span>
          </div>
          <p class="db-seeding-desc">
            {#if dbRecipeCount === 0}
              Database currently contains <strong>0 recipes</strong>. You can seed the curated starter recipe collection.
            {:else}
              Database contains <strong>{dbRecipeCount} {dbRecipeCount === 1 ? 'recipe' : 'recipes'}</strong>.
              Seeding should really only be done if there are 0 recipes in the DB.
            {/if}
          </p>
        </div>
        <div class="db-seeding-action">
          <button
            class="btn btn-seed {dbRecipeCount > 0 ? 'btn-seed-verify' : 'btn-seed-ready'}"
            on:click={handleSeedClick}
            disabled={seeding || loadingDbStats}
            title={dbRecipeCount > 0 ? 'Verification required: database already has recipes' : 'Seed curated recipes'}
          >
            <span>{seeding ? '🌱 Seeding Recipes...' : '🌱 Seed Recipes'}</span>
          </button>
        </div>
      </div>

      <!-- Controls Toolbar -->
      <div class="admin-toolbar">
        <!-- Live Search -->
        <div class="search-field">
          <span class="search-ico">🔍</span>
          <input
            type="text"
            placeholder="Search users by name or email..."
            class="search-ctrl"
            value={searchQuery}
            on:input={handleSearchInput}
          />
          {#if searchQuery}
            <button class="clear-search-btn" on:click={clearSearch} title="Clear search">✕</button>
          {/if}
        </div>

        <!-- Role Filter Tabs -->
        <div class="filter-pills">
          <button
            class="pill-btn {selectedRoleFilter === 'All' ? 'active' : ''}"
            on:click={() => handleFilterTab('All')}
          >
            All ({metrics.total})
          </button>
          <button
            class="pill-btn {selectedRoleFilter === 'Admin' ? 'active active-purple' : ''}"
            on:click={() => handleFilterTab('Admin')}
          >
            👑 Admins ({metrics.admin_count})
          </button>
          <button
            class="pill-btn {selectedRoleFilter === 'Editor' ? 'active active-emerald' : ''}"
            on:click={() => handleFilterTab('Editor')}
          >
            🍳 Editors ({metrics.editor_count})
          </button>
          <button
            class="pill-btn {selectedRoleFilter === 'Viewer' ? 'active active-slate' : ''}"
            on:click={() => handleFilterTab('Viewer')}
          >
            👁️ Viewers ({metrics.viewer_count})
          </button>
        </div>

        <!-- Add / Pre-authorize User Button -->
        <button
          class="btn btn-primary btn-sm btn-provision"
          on:click={() => (isProvisionOpen = !isProvisionOpen)}
        >
          <span>{isProvisionOpen ? '✕ Cancel' : '+ Pre-authorize User'}</span>
        </button>
      </div>

      <!-- Pre-authorize Drawer / Form -->
      {#if isProvisionOpen}
        <div class="provision-card animate-fade-in">
          <div class="provision-header">
            <div class="provision-title">
              <span>⚡ Pre-authorize Account by Email</span>
            </div>
            <p class="provision-desc">
              Grant permissions ahead of time. When this user logs in with Google, their designated role is already active.
            </p>
          </div>

          <div class="provision-fields">
            <div class="form-group flex-2">
              <label for="new-user-email">User Email Address *</label>
              <input
                id="new-user-email"
                type="email"
                placeholder="e.g. chef.alex@gmail.com"
                class="form-input"
                bind:value={newEmail}
              />
            </div>

            <div class="form-group flex-2">
              <label for="new-user-name">Full Name (Optional)</label>
              <input
                id="new-user-name"
                type="text"
                placeholder="e.g. Alex Rivera"
                class="form-input"
                bind:value={newName}
              />
            </div>

            <div class="form-group flex-1">
              <label for="new-user-role">Role to Assign</label>
              <select id="new-user-role" class="form-select" bind:value={newRole}>
                <option value="editor">🍳 Editor (Recipe creation)</option>
                <option value="admin">👑 Admin (Full permissions)</option>
                <option value="viewer">👁️ Viewer (Read only)</option>
              </select>
            </div>

            <div class="form-group form-actions">
              <span class="opacity-0" aria-hidden="true">&nbsp;</span>
              <button
                class="btn btn-primary"
                on:click={handleProvision}
                disabled={provisioning || !newEmail}
              >
                <span>{provisioning ? 'Authorizing...' : 'Grant Access'}</span>
              </button>
            </div>
          </div>
        </div>
      {/if}

      <!-- User List Table / Cards -->
      <div class="users-container">
        {#if loading && users.length === 0}
          <div class="loading-state">
            <div class="spinner"></div>
            <span>Fetching user authorization records...</span>
          </div>
        {:else if users.length === 0}
          <div class="empty-state">
            <div class="empty-icon">🔍</div>
            <h3>No users found</h3>
            <p>
              {#if searchQuery}
                No registered accounts matched "{searchQuery}".
              {:else}
                No users found under the "{selectedRoleFilter}" category.
              {/if}
            </p>
            {#if searchQuery}
              <button class="btn btn-secondary btn-sm" on:click={clearSearch}>
                Clear Search Filter
              </button>
            {/if}
          </div>
        {:else}
          <div class="users-table-wrap">
            <table class="users-table">
              <thead>
                <tr>
                  <th>User & Account</th>
                  <th>Assigned Role</th>
                  <th>Can Modify Recipes</th>
                  <th>First Joined</th>
                  <th>Last Login</th>
                  <th class="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {#each users as user (user.id)}
                  <tr class="user-row {savingUserId === user.id ? 'row-saving' : ''}">
                    <!-- User & Account Details -->
                    <td class="col-user">
                      <div class="user-cell">
                        {#if user.picture}
                          <img src={user.picture} alt={user.name} class="avatar-img" />
                        {:else}
                          <div class="avatar-fallback {user.role === 'admin' ? 'bg-purple' : user.can_edit ? 'bg-emerald' : 'bg-slate'}">
                            {user.name ? user.name.charAt(0).toUpperCase() : '👤'}
                          </div>
                        {/if}
                        <div class="user-meta">
                          <div class="user-name-line">
                            <span class="user-name">{user.name || 'Unnamed User'}</span>
                            {#if user.id === $currentUser?.id}
                              <span class="badge-pill badge-you">You</span>
                            {/if}
                            {#if user.is_bootstrap}
                              <span
                                class="badge-pill badge-bootstrap"
                                title="Configured as initial privileged administrator in server environment"
                              >
                                ⚡ .env Bootstrap
                              </span>
                            {/if}
                          </div>
                          <span class="user-email">{user.email}</span>
                        </div>
                      </div>
                    </td>

                    <!-- Assigned Role Dropdown -->
                    <td class="col-role">
                      <div class="role-selector-wrap">
                        <select
                          class="role-select {user.role === 'admin' ? 'select-admin' : user.role === 'editor' ? 'select-editor' : 'select-viewer'}"
                          value={user.role}
                          on:change={(e) => handleRoleChange(user, e)}
                          disabled={savingUserId === user.id || user.is_bootstrap}
                          title={user.is_bootstrap ? 'Role is configured via server environment' : 'Change user role'}
                        >
                          <option value="admin">👑 Administrator</option>
                          <option value="editor">🍳 Recipe Editor</option>
                          <option value="viewer">👁️ Read-Only Viewer</option>
                        </select>
                        {#if savingUserId === user.id}
                          <span class="saving-dot" title="Saving permissions..."></span>
                        {/if}
                      </div>
                    </td>

                    <!-- Recipe Editing Toggle -->
                    <td class="col-edit">
                      <label class="switch-toggle" title="Direct recipe add/edit/delete capability">
                        <input
                          type="checkbox"
                          checked={user.can_edit}
                          on:change={(e) => handleToggleEdit(user, e)}
                          disabled={savingUserId === user.id || user.is_bootstrap || user.role === 'admin'}
                        />
                        <span class="slider"></span>
                      </label>
                      <span class="toggle-status {user.can_edit ? 'status-enabled' : 'status-disabled'}">
                        {user.can_edit ? 'Allowed' : 'Blocked'}
                      </span>
                    </td>

                    <!-- Timestamps -->
                    <td class="col-date">{formatDate(user.created_at)}</td>
                    <td class="col-date">{formatDate(user.last_login)}</td>

                    <!-- Actions -->
                    <td class="col-actions text-right">
                      {#if user.id !== $currentUser?.id && !user.is_bootstrap}
                        <button
                          class="btn-icon-danger"
                          on:click={() => handleDeleteUser(user)}
                          disabled={deletingUserId === user.id}
                          title="Remove user account"
                        >
                          🗑️
                        </button>
                      {:else}
                        <span class="protected-icon" title="Protected account">🔒</span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="admin-footer">
        <div class="footer-note">
          <span class="lock-icon">🔐</span>
          <span>
            Initial privileged administrator is seeded from server environment. Newly assigned roles take effect immediately across all devices.
          </span>
        </div>
        <button class="btn btn-secondary" on:click={closeModal}>
          Done
        </button>
      </div>
    </div>
  </div>

  <!-- Seed Verification Modal -->
  {#if isSeedConfirmOpen}
    <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
    <div
      class="verify-backdrop animate-fade-in"
      on:click={closeSeedConfirm}
      on:keydown={(e) => e.key === 'Escape' && closeSeedConfirm()}
      role="presentation"
    >
      <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
      <div
        class="verify-dialog"
        on:click|stopPropagation
        on:keydown|stopPropagation
        role="dialog"
        aria-modal="true"
        aria-labelledby="seed-verify-title"
      >
        <div class="verify-header">
          <div class="verify-icon-wrap">
            <span>⚠️</span>
          </div>
          <div class="verify-header-text">
            <h3 id="seed-verify-title" class="verify-title">Verification Required</h3>
            <span class="verify-subtitle">Database Already Contains Recipes</span>
          </div>
          <button class="close-btn" on:click={closeSeedConfirm} aria-label="Cancel">✕</button>
        </div>

        <div class="verify-content">
          <div class="verify-warning-card">
            <p class="verify-alert-text">
              There are currently <strong>{dbRecipeCount} {dbRecipeCount === 1 ? 'recipe' : 'recipes'}</strong> in the database.
            </p>
            <p class="verify-sub-alert">
              Seeding should really only be done if there are <strong>0 recipes</strong> in the DB.
              Proceeding will insert additional sample recipes alongside your existing data.
            </p>
          </div>

          <div class="verify-field">
            <label for="verify-seed-input" class="verify-label">
              To confirm this action, please type <strong class="type-target">SEED</strong>:
            </label>
            <input
              id="verify-seed-input"
              type="text"
              class="verify-text-input"
              placeholder="Type SEED to confirm"
              bind:value={seedVerifyInput}
              autocomplete="off"
              on:keydown={(e) => {
                if (e.key === 'Enter' && seedVerifyInput.trim().toUpperCase() === 'SEED') {
                  executeVerifiedSeed();
                }
              }}
            />
          </div>
        </div>

        <div class="verify-actions">
          <button class="btn btn-secondary" on:click={closeSeedConfirm} disabled={seeding}>
            Cancel
          </button>
          <button
            class="btn btn-danger-action"
            disabled={seedVerifyInput.trim().toUpperCase() !== 'SEED' || seeding}
            on:click={executeVerifiedSeed}
          >
            {seeding ? '🌱 Seeding...' : '⚠️ Force Seed Recipes'}
          </button>
        </div>
      </div>
    </div>
  {/if}
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.75);
    backdrop-filter: blur(10px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1.5rem;
  }

  .admin-card {
    background: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 1.25rem;
    width: 100%;
    max-width: 1080px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
    overflow: hidden;
  }

  /* Header */
  .admin-header {
    padding: 1.35rem 1.75rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(30, 41, 59, 0.4);
  }

  .header-main {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .admin-icon-glow {
    width: 48px;
    height: 48px;
    border-radius: 1rem;
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.25) 0%, rgba(99, 102, 241, 0.25) 100%);
    border: 1px solid rgba(168, 85, 247, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.4rem;
    box-shadow: 0 0 15px rgba(124, 58, 237, 0.2);
  }

  .header-text {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .header-top-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .admin-title {
    font-family: var(--font-serif);
    font-size: 1.35rem;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.01em;
  }

  .badge-env-notice {
    font-size: 0.68rem;
    font-weight: 700;
    padding: 0.15rem 0.55rem;
    border-radius: 9999px;
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.3);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .admin-subtitle {
    font-size: 0.82rem;
    color: #94a3b8;
  }

  .close-btn {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 1.25rem;
    cursor: pointer;
    width: 34px;
    height: 34px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
  }

  /* Metrics Grid */
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    padding: 1.25rem 1.75rem 0.75rem;
  }

  .metric-card {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 0.85rem;
    padding: 0.85rem 1.15rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    transition: transform 0.2s;
  }

  .metric-card:hover {
    transform: translateY(-2px);
    border-color: rgba(255, 255, 255, 0.18);
  }

  .metric-info {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .metric-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #94a3b8;
  }

  .metric-value {
    font-size: 1.45rem;
    font-weight: 800;
    color: #f8fafc;
  }

  .metric-icon {
    font-size: 1.5rem;
    opacity: 0.85;
  }

  .text-purple {
    color: #c084fc;
  }

  .text-emerald {
    color: #34d399;
  }

  .text-slate {
    color: #cbd5e1;
  }

  /* Toolbar */
  .admin-toolbar {
    padding: 0.75rem 1.75rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .search-field {
    flex: 1;
    min-width: 240px;
    position: relative;
    display: flex;
    align-items: center;
  }

  .search-ico {
    position: absolute;
    left: 0.85rem;
    font-size: 0.85rem;
    color: #64748b;
    pointer-events: none;
  }

  .search-ctrl {
    width: 100%;
    padding: 0.55rem 2rem 0.55rem 2.25rem;
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 9999px;
    color: #f1f5f9;
    font-size: 0.85rem;
    outline: none;
    transition: all 0.2s;
  }

  .search-ctrl:focus {
    border-color: #8b5cf6;
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.25);
    background: #1e293b;
  }

  .clear-search-btn {
    position: absolute;
    right: 0.75rem;
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 0.8rem;
    cursor: pointer;
  }

  .filter-pills {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    background: rgba(30, 41, 59, 0.6);
    padding: 0.25rem;
    border-radius: 9999px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .pill-btn {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 0.76rem;
    font-weight: 600;
    padding: 0.35rem 0.75rem;
    border-radius: 9999px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .pill-btn:hover {
    color: #f1f5f9;
  }

  .pill-btn.active {
    background: #334155;
    color: #ffffff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  }

  .pill-btn.active-purple {
    background: rgba(147, 51, 234, 0.3);
    color: #e9d5ff;
    border: 1px solid rgba(168, 85, 247, 0.4);
  }

  .pill-btn.active-emerald {
    background: rgba(16, 185, 129, 0.25);
    color: #a7f3d0;
    border: 1px solid rgba(16, 185, 129, 0.4);
  }

  .pill-btn.active-slate {
    background: rgba(100, 116, 139, 0.3);
    color: #f1f5f9;
    border: 1px solid rgba(148, 163, 184, 0.4);
  }

  .btn-provision {
    background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
    box-shadow: 0 2px 4px rgba(124, 58, 237, 0.3);
  }

  /* Pre-authorize Drawer */
  .provision-card {
    margin: 0.85rem 1.75rem 0.25rem;
    padding: 1.15rem 1.35rem;
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 0.85rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  }

  .provision-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .provision-desc {
    font-size: 0.78rem;
    color: #94a3b8;
    margin-top: 0.15rem;
    margin-bottom: 0.85rem;
  }

  .provision-fields {
    display: flex;
    gap: 0.85rem;
    align-items: flex-end;
    flex-wrap: wrap;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .form-group label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #cbd5e1;
  }

  .flex-1 { flex: 1; min-width: 160px; }
  .flex-2 { flex: 2; min-width: 200px; }
  .opacity-0 { opacity: 0; }

  /* User List Container */
  .users-container {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem 1.75rem;
    min-height: 280px;
  }

  .users-table-wrap {
    overflow-x: auto;
  }

  .users-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0 0.5rem;
    font-size: 0.84rem;
  }

  .users-table th {
    text-align: left;
    padding: 0.5rem 1rem;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b;
  }

  .user-row {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 0.75rem;
    transition: all 0.15s ease;
  }

  .user-row:hover {
    background: rgba(30, 41, 59, 0.85);
    border-color: rgba(255, 255, 255, 0.14);
  }

  .user-row td {
    padding: 0.85rem 1rem;
    vertical-align: middle;
  }

  .user-row td:first-child {
    border-top-left-radius: 0.75rem;
    border-bottom-left-radius: 0.75rem;
  }

  .user-row td:last-child {
    border-top-right-radius: 0.75rem;
    border-bottom-right-radius: 0.75rem;
  }

  .row-saving {
    opacity: 0.6;
    pointer-events: none;
  }

  /* User Cell */
  .user-cell {
    display: flex;
    align-items: center;
    gap: 0.85rem;
  }

  .avatar-img {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid rgba(255, 255, 255, 0.15);
  }

  .avatar-fallback {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    color: white;
    font-size: 0.95rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid rgba(255, 255, 255, 0.15);
  }

  .bg-purple { background: #7c3aed; }
  .bg-emerald { background: #059669; }
  .bg-slate { background: #475569; }

  .user-meta {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .user-name-line {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
  }

  .user-name {
    font-weight: 700;
    color: #f1f5f9;
  }

  .user-email {
    font-size: 0.74rem;
    color: #94a3b8;
  }

  .badge-pill {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.1rem 0.45rem;
    border-radius: 9999px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .badge-you {
    background: rgba(59, 130, 246, 0.2);
    color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.35);
  }

  .badge-bootstrap {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.35);
  }

  /* Role Selector */
  .role-selector-wrap {
    display: flex;
    align-items: center;
    gap: 0.45rem;
  }

  .role-select {
    padding: 0.4rem 0.75rem;
    border-radius: 0.5rem;
    font-size: 0.8rem;
    font-weight: 600;
    border: 1px solid rgba(255, 255, 255, 0.12);
    outline: none;
    cursor: pointer;
    background-color: #1e293b;
    color: #f8fafc;
    transition: all 0.2s;
  }

  .role-select:hover:not(:disabled) {
    border-color: #8b5cf6;
  }

  .role-select:disabled {
    opacity: 0.75;
    cursor: not-allowed;
  }

  .select-admin {
    background: rgba(147, 51, 234, 0.15);
    color: #d8b4fe;
    border-color: rgba(168, 85, 247, 0.35);
  }

  .select-editor {
    background: rgba(16, 185, 129, 0.15);
    color: #6ee7b7;
    border-color: rgba(16, 185, 129, 0.35);
  }

  .select-viewer {
    background: rgba(100, 116, 139, 0.15);
    color: #cbd5e1;
    border-color: rgba(148, 163, 184, 0.25);
  }

  .saving-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #8b5cf6;
    animation: pulse 1s infinite alternate;
  }

  @keyframes pulse {
    from { opacity: 0.3; }
    to { opacity: 1; }
  }

  /* Switch Toggle */
  .switch-toggle {
    position: relative;
    display: inline-block;
    width: 36px;
    height: 20px;
    vertical-align: middle;
  }

  .switch-toggle input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  .slider {
    position: absolute;
    cursor: pointer;
    inset: 0;
    background-color: #334155;
    transition: 0.2s;
    border-radius: 34px;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .slider:before {
    position: absolute;
    content: "";
    height: 14px;
    width: 14px;
    left: 2px;
    bottom: 2px;
    background-color: white;
    transition: 0.2s;
    border-radius: 50%;
  }

  input:checked + .slider {
    background-color: #10b981;
  }

  input:checked + .slider:before {
    transform: translateX(16px);
  }

  input:disabled + .slider {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .toggle-status {
    font-size: 0.72rem;
    font-weight: 600;
    margin-left: 0.4rem;
  }

  .status-enabled {
    color: #34d399;
  }

  .status-disabled {
    color: #64748b;
  }

  .col-date {
    font-size: 0.76rem;
    color: #94a3b8;
  }

  .text-right {
    text-align: right;
  }

  .btn-icon-danger {
    background: transparent;
    border: none;
    font-size: 0.95rem;
    cursor: pointer;
    padding: 0.35rem 0.5rem;
    border-radius: 0.4rem;
    transition: all 0.15s;
    opacity: 0.7;
  }

  .btn-icon-danger:hover {
    background: rgba(239, 68, 68, 0.2);
    opacity: 1;
    transform: scale(1.1);
  }

  .protected-icon {
    font-size: 0.85rem;
    opacity: 0.5;
  }

  /* Empty & Loading states */
  .loading-state, .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3.5rem 1rem;
    color: #94a3b8;
    gap: 0.75rem;
    text-align: center;
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid rgba(255, 255, 255, 0.1);
    border-top-color: #8b5cf6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .empty-icon {
    font-size: 2rem;
  }

  .empty-state h3 {
    font-size: 1.1rem;
    color: #f1f5f9;
  }

  .empty-state p {
    font-size: 0.85rem;
    max-width: 360px;
  }

  /* Footer */
  .admin-footer {
    padding: 1rem 1.75rem;
    background: rgba(30, 41, 59, 0.4);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .footer-note {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.74rem;
    color: #94a3b8;
    max-width: 720px;
  }

  @media (max-width: 860px) {
    .metrics-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 600px) {
    .metrics-grid {
      grid-template-columns: 1fr;
    }
  }

  /* Database Seeding Card */
  .db-seeding-card {
    background: rgba(30, 41, 59, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 0.85rem;
    margin: 0.25rem 1.75rem 1rem;
    padding: 0.85rem 1.25rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1.25rem;
    transition: all 0.2s ease;
  }

  .db-seeding-card:hover {
    border-color: rgba(255, 255, 255, 0.16);
    background: rgba(30, 41, 59, 0.6);
  }

  .db-seeding-info {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .db-seeding-badge-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .db-icon {
    font-size: 1.15rem;
  }

  .db-card-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .badge-db-count {
    font-size: 0.72rem;
    font-weight: 700;
    padding: 0.15rem 0.55rem;
    border-radius: 9999px;
    letter-spacing: 0.03em;
  }

  .badge-db-empty {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.35);
  }

  .badge-db-populated {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.35);
  }

  .db-seeding-desc {
    font-size: 0.82rem;
    color: #94a3b8;
    line-height: 1.4;
  }

  .db-seeding-desc strong {
    color: #e2e8f0;
  }

  .db-seeding-action {
    flex-shrink: 0;
  }

  .btn-seed {
    padding: 0.55rem 1.15rem;
    font-size: 0.85rem;
    font-weight: 600;
    border-radius: 0.65rem;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    transition: all 0.2s ease;
  }

  .btn-seed-ready {
    background: linear-gradient(135deg, #059669 0%, #10b981 100%);
    color: #ffffff;
    border: 1px solid rgba(52, 211, 153, 0.3);
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
  }

  .btn-seed-ready:hover:not(:disabled) {
    background: linear-gradient(135deg, #047857 0%, #059669 100%);
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(16, 185, 129, 0.3);
  }

  .btn-seed-verify {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.35);
  }

  .btn-seed-verify:hover:not(:disabled) {
    background: rgba(245, 158, 11, 0.25);
    color: #fef3c7;
    border-color: rgba(245, 158, 11, 0.5);
    transform: translateY(-1px);
  }

  .btn-seed:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none !important;
  }

  /* Seed Verification Modal */
  .verify-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1100;
    padding: 1.5rem;
  }

  .verify-dialog {
    background: #0f172a;
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: 1.15rem;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8), 0 0 25px rgba(245, 158, 11, 0.15);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .verify-header {
    padding: 1.15rem 1.35rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    gap: 0.85rem;
    background: rgba(30, 41, 59, 0.5);
  }

  .verify-icon-wrap {
    width: 42px;
    height: 42px;
    border-radius: 0.75rem;
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.3rem;
    flex-shrink: 0;
  }

  .verify-header-text {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .verify-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .verify-subtitle {
    font-size: 0.75rem;
    color: #fbbf24;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .verify-content {
    padding: 1.25rem 1.35rem;
    display: flex;
    flex-direction: column;
    gap: 1.15rem;
  }

  .verify-warning-card {
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.25);
    border-radius: 0.75rem;
    padding: 0.9rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }

  .verify-alert-text {
    font-size: 0.88rem;
    font-weight: 600;
    color: #fef3c7;
    line-height: 1.4;
  }

  .verify-sub-alert {
    font-size: 0.8rem;
    color: #cbd5e1;
    line-height: 1.45;
  }

  .verify-field {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }

  .verify-label {
    font-size: 0.82rem;
    color: #94a3b8;
  }

  .type-target {
    color: #fbbf24;
    background: rgba(245, 158, 11, 0.15);
    padding: 0.1rem 0.35rem;
    border-radius: 0.3rem;
    font-family: monospace;
    font-size: 0.9rem;
  }

  .verify-text-input {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 0.6rem;
    padding: 0.65rem 0.9rem;
    color: #ffffff;
    font-size: 0.95rem;
    letter-spacing: 0.05em;
    font-weight: 600;
    outline: none;
    transition: all 0.2s ease;
  }

  .verify-text-input:focus {
    border-color: #fbbf24;
    box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.25);
  }

  .verify-actions {
    padding: 1rem 1.35rem;
    background: rgba(30, 41, 59, 0.4);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.75rem;
  }

  .btn-danger-action {
    background: linear-gradient(135deg, #d97706 0%, #b45309 100%);
    color: #ffffff;
    border: 1px solid rgba(245, 158, 11, 0.4);
    padding: 0.55rem 1.1rem;
    font-size: 0.85rem;
    font-weight: 600;
    border-radius: 0.65rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-danger-action:hover:not(:disabled) {
    background: linear-gradient(135deg, #b45309 0%, #92400e 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(180, 83, 9, 0.3);
  }

  .btn-danger-action:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    transform: none;
  }

  @media (max-width: 600px) {
    .db-seeding-card {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.85rem;
    }

    .db-seeding-action {
      width: 100%;
    }

    .btn-seed {
      width: 100%;
      justify-content: center;
    }
  }
</style>
