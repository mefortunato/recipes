<script>
  import { onMount } from 'svelte';
  import { isAuthModalOpen, currentUser, authConfig, showToast } from '../stores';
  import { api } from '../api';

  let isLoading = false;
  let errorMessage = '';
  let isGoogleGisRendered = false;
  let customDevEmail = '';
  let customDevName = '';

  function closeModal() {
    isAuthModalOpen.set(false);
    errorMessage = '';
  }

  function initializeGis() {
    if (typeof window === 'undefined') return;
    const w = window;
    const clientId = $authConfig?.google_client_id;
    if (w.google?.accounts?.id && clientId) {
      try {
        w.google.accounts.id.initialize({
          client_id: clientId,
          callback: handleGisCredentialResponse,
        });
        const btnContainer = document.getElementById('google-gis-btn-container');
        if (btnContainer) {
          btnContainer.innerHTML = '';
          w.google.accounts.id.renderButton(btnContainer, {
            theme: 'filled_blue',
            size: 'large',
            text: 'continue_with',
            shape: 'pill',
            width: 320,
          });
          isGoogleGisRendered = true;
        }
      } catch (err) {
        console.warn('GIS initialization error:', err);
      }
    }
  }

  $: if ($isAuthModalOpen) {
    errorMessage = '';
    // Small timeout to ensure DOM container is mounted
    setTimeout(initializeGis, 60);
  }

  async function handleGisCredentialResponse(response) {
    if (!response?.credential) return;
    isLoading = true;
    errorMessage = '';
    try {
      const res = await api.verifyGoogleCredential(response.credential);
      if (res?.user) {
        currentUser.set(res.user);
        showToast(`Welcome back, ${res.user.name || res.user.email}! 🎉`, 'success');
        closeModal();
      }
    } catch (err) {
      errorMessage = err.message || 'Google sign-in failed. Please try again.';
    } finally {
      isLoading = false;
    }
  }

  function handleFallbackOAuth() {
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1';
    window.location.href = `${apiBase}/auth/google/login`;
  }

  async function handleDevLogin(name, email) {
    isLoading = true;
    errorMessage = '';
    try {
      const res = await api.verifyGoogleCredential({
        google_id: `dev_${email.replace('@', '_').replace('.', '_')}`,
        name,
        email,
      });
      if (res?.user) {
        currentUser.set(res.user);
        showToast(`Signed in as ${res.user.name} (${res.user.role}) 🚀`, 'success');
        closeModal();
      }
    } catch (err) {
      errorMessage = err.message || 'Dev login failed.';
    } finally {
      isLoading = false;
    }
  }

  async function handleCustomDevSubmit() {
    if (!customDevEmail || !customDevEmail.includes('@')) {
      errorMessage = 'Please enter a valid email address';
      return;
    }
    const name = customDevName.trim() || customDevEmail.split('@')[0];
    await handleDevLogin(name, customDevEmail);
  }
</script>

{#if $isAuthModalOpen}
  <div
    class="modal-backdrop"
    on:click={closeModal}
    on:keydown={(e) => e.key === 'Escape' && closeModal()}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <div
      class="auth-card animate-fade-in"
      on:click|stopPropagation={() => {}}
      on:keydown|stopPropagation={() => {}}
      role="document"
      tabindex="-1"
    >
      <!-- Header -->
      <div class="auth-header">
        <div class="badge-icon">🔐</div>
        <h2 class="auth-title">Chef & Kitchen Access</h2>
        <p class="auth-subtitle">Sign in to add, edit, or manage vault recipes</p>
        <button class="close-btn" on:click={closeModal} aria-label="Close modal">✕</button>
      </div>

      <!-- Body -->
      <div class="auth-body">
        {#if errorMessage}
          <div class="error-banner">
            <span class="error-icon">⚠️</span>
            <span class="error-text">{errorMessage}</span>
          </div>
        {/if}

        <!-- Official Google Sign-in Section (GIS) -->
        <div class="google-auth-section">
          <!-- Container for Google's official 1-click button -->
          <div id="google-gis-btn-container" class="gis-button-wrapper"></div>

          <!-- Fallback button if GIS script blocked or not initialized -->
          {#if !isGoogleGisRendered}
            <button class="google-btn" on:click={handleFallbackOAuth} disabled={isLoading}>
              <div class="google-icon-wrapper">
                <svg width="22" height="22" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                </svg>
              </div>
              <div class="google-btn-text">
                <span class="btn-primary-text">Continue with Google</span>
                <span class="btn-sub-text">1-click secure authentication</span>
              </div>
              <span class="btn-arrow">→</span>
            </button>
          {/if}
        </div>

        <!-- Development Quick Profiles (only if dev_login_enabled in .env) -->
        {#if $authConfig?.dev_login_enabled}
          <div class="dev-section">
            <div class="dev-header">
              <span class="dev-badge">DEV MODE</span>
              <span class="dev-subtitle">Instant Test Profiles</span>
            </div>
            <div class="dev-btn-group">
              <button
                class="btn-dev-profile"
                on:click={() => handleDevLogin('Chef Auguste', 'chef.auguste@example.com')}
                disabled={isLoading}
              >
                <span class="dev-avatar">A</span>
                <div class="dev-info">
                  <span class="dev-name">Auguste (Admin)</span>
                  <span class="dev-email">chef.auguste@example.com</span>
                </div>
              </button>
              <button
                class="btn-dev-profile"
                on:click={() => handleDevLogin('Sous Chef Maria', 'maria.cook@example.com')}
                disabled={isLoading}
              >
                <span class="dev-avatar dev-avatar-editor">M</span>
                <div class="dev-info">
                  <span class="dev-name">Maria (Editor)</span>
                  <span class="dev-email">maria.cook@example.com</span>
                </div>
              </button>
            </div>

            <!-- Custom Dev Email Input -->
            <div class="custom-dev-box">
              <input
                type="email"
                bind:value={customDevEmail}
                placeholder="custom.chef@example.com"
                class="dev-input"
                disabled={isLoading}
              />
              <button
                class="btn-dev-submit"
                on:click={handleCustomDevSubmit}
                disabled={isLoading || !customDevEmail}
              >
                Test Sign In
              </button>
            </div>
          </div>
        {/if}

        <!-- Access control explanation -->
        <div class="permissions-notice">
          <div class="notice-title">🛡️ Role-Based Access Control</div>
          <p class="notice-text">
            Public visitors have read-only access. Authorized editors can create and update recipes. Privileged administrators can manage user permissions in the Admin Panel.
          </p>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.75);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1.5rem;
  }

  .auth-card {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 1.25rem;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    overflow: hidden;
    position: relative;
  }

  .auth-header {
    background: linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.95));
    padding: 2rem 2rem 1.25rem;
    text-align: center;
    position: relative;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .badge-icon {
    font-size: 2.25rem;
    margin-bottom: 0.5rem;
  }

  .auth-title {
    font-size: 1.4rem;
    font-weight: 700;
    color: #f8fafc;
    margin: 0 0 0.35rem;
    letter-spacing: -0.02em;
  }

  .auth-subtitle {
    color: #94a3b8;
    font-size: 0.9rem;
    margin: 0;
  }

  .close-btn {
    position: absolute;
    top: 1rem;
    right: 1rem;
    background: rgba(255, 255, 255, 0.05);
    border: none;
    color: #94a3b8;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    font-size: 1rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }

  .close-btn:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #fff;
  }

  .auth-body {
    padding: 1.75rem 2rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .error-banner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #fca5a5;
    padding: 0.75rem 1rem;
    border-radius: 0.5rem;
    font-size: 0.85rem;
  }

  .google-auth-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
  }

  .gis-button-wrapper {
    display: flex;
    justify-content: center;
    width: 100%;
    min-height: 44px;
  }

  .google-btn {
    display: flex;
    align-items: center;
    gap: 1rem;
    width: 100%;
    padding: 0.85rem 1.25rem;
    background: #ffffff;
    color: #1e293b;
    border: 1px solid #e2e8f0;
    border-radius: 0.75rem;
    cursor: pointer;
    font-weight: 600;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    text-align: left;
  }

  .google-btn:hover {
    background: #f8fafc;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.15);
    transform: translateY(-1px);
  }

  .google-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }

  .google-icon-wrapper {
    flex-shrink: 0;
    display: flex;
    align-items: center;
  }

  .google-btn-text {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .btn-primary-text {
    font-size: 1rem;
    color: #1e293b;
    font-weight: 700;
  }

  .btn-sub-text {
    font-size: 0.75rem;
    color: #64748b;
  }

  .btn-arrow {
    font-size: 1.2rem;
    color: #64748b;
    font-weight: 600;
  }

  /* Dev Section */
  .dev-section {
    background: rgba(15, 23, 42, 0.5);
    border: 1px dashed rgba(56, 189, 248, 0.3);
    border-radius: 0.75rem;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .dev-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .dev-badge {
    background: #0284c7;
    color: #ffffff;
    font-size: 0.65rem;
    font-weight: 800;
    letter-spacing: 0.05em;
    padding: 0.2rem 0.45rem;
    border-radius: 4px;
  }

  .dev-subtitle {
    font-size: 0.75rem;
    color: #94a3b8;
  }

  .dev-btn-group {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }

  .btn-dev-profile {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 0.5rem 0.65rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-dev-profile:hover {
    background: rgba(56, 189, 248, 0.12);
    border-color: #38bdf8;
    transform: translateY(-1px);
  }

  .dev-avatar {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: linear-gradient(135deg, #0284c7, #2563eb);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    flex-shrink: 0;
  }

  .dev-avatar-editor {
    background: linear-gradient(135deg, #7c3aed, #db2777);
  }

  .dev-info {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dev-name {
    font-size: 0.78rem;
    font-weight: 600;
    color: #f1f5f9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .dev-email {
    font-size: 0.65rem;
    color: #64748b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .custom-dev-box {
    display: flex;
    gap: 0.5rem;
  }

  .dev-input {
    flex: 1;
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 0.45rem 0.65rem;
    color: #fff;
    font-size: 0.75rem;
    outline: none;
    transition: border-color 0.2s;
  }

  .dev-input:focus {
    border-color: #38bdf8;
  }

  .btn-dev-submit {
    background: #0284c7;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 0.45rem 0.75rem;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background 0.2s;
  }

  .btn-dev-submit:hover {
    background: #0369a1;
  }

  .btn-dev-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Permissions Notice */
  .permissions-notice {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 0.75rem;
    padding: 1rem;
  }

  .notice-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #38bdf8;
    margin-bottom: 0.35rem;
  }

  .notice-text {
    font-size: 0.82rem;
    color: #94a3b8;
    line-height: 1.45;
    margin: 0;
  }
</style>
