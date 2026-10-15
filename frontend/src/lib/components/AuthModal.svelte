<script>
  import { isAuthModalOpen, currentUser, authConfig, showToast } from '../stores';

  function closeModal() {
    isAuthModalOpen.set(false);
  }

  function handleGoogleOAuth() {
    const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1';
    window.location.href = `${apiBase}/auth/google/login`;
  }
</script>

{#if $isAuthModalOpen}
  <div class="modal-backdrop" on:click={closeModal} on:keydown={(e) => e.key === 'Escape' && closeModal()} role="dialog" aria-modal="true" tabindex="-1">
    <div class="auth-card animate-fade-in" on:click|stopPropagation on:keydown|stopPropagation role="document" tabindex="-1">
      <!-- Header -->
      <div class="auth-header">
        <div class="badge-icon">🔐</div>
        <h2 class="auth-title">Chef & Kitchen Access</h2>
        <p class="auth-subtitle">Sign in to add, edit, or manage vault recipes</p>
        <button class="close-btn" on:click={closeModal} aria-label="Close modal">✕</button>
      </div>

      <!-- Body -->
      <div class="auth-body">
        <!-- Google Sign-in Card -->
        <button class="google-btn" on:click={handleGoogleOAuth}>
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
            <span class="btn-sub-text">1-click official Google authentication</span>
          </div>
          <span class="btn-arrow">→</span>
        </button>

        <!-- Access control explanation -->
        <div class="permissions-notice">
          <div class="notice-title">🛡️ Role-Based Access Control</div>
          <p class="notice-text">
            Public visitors have read-only access. Authorized editors can create and update recipes. Privileged administrators can manage user permissions and roles in the Admin Panel.
          </p>
          {#if $authConfig?.allowed_editor_emails && $authConfig.allowed_editor_emails.length > 0}
            <div class="allowed-list">
              <span class="allowed-label">Bootstrap Admin (.env):</span>
              <span class="allowed-emails">
                {$authConfig.allowed_editor_emails.includes('*') ? 'All authenticated Google users' : $authConfig.allowed_editor_emails.join(', ')}
              </span>
            </div>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.7);
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
    margin: 0 0 0.5rem;
  }

  .allowed-list {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    font-size: 0.78rem;
    border-top: 1px dashed rgba(255, 255, 255, 0.1);
    padding-top: 0.5rem;
  }

  .allowed-label {
    color: #cbd5e1;
    font-weight: 600;
  }

  .allowed-emails {
    color: #10b981;
    word-break: break-all;
    font-family: monospace;
  }

</style>
