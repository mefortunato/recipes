<script>
  import { toast } from '../stores';
</script>

{#if $toast.show}
  <div class="toast-container">
    <div class="toast-box toast-{$toast.type} animate-fade-in">
      <span class="toast-icon">
        {#if $toast.type === 'success'}✅{/if}
        {#if $toast.type === 'error'}⚠️{/if}
        {#if $toast.type === 'info'}ℹ️{/if}
      </span>
      <span class="toast-msg">{$toast.message}</span>
    </div>
  </div>
{/if}

<style>
  .toast-container {
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    z-index: 100;
    pointer-events: none;
  }

  .toast-box {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    padding: 0.75rem 1.25rem;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-xl);
    font-size: 0.9rem;
    font-weight: 600;
    background: white;
    border: 1px solid var(--border-color);
  }

  .toast-success {
    border-color: #86efac;
    background: #f0fdf4;
    color: #166534;
  }

  .toast-error {
    border-color: #fca5a5;
    background: #fef2f2;
    color: #991b1b;
  }

  .toast-info {
    border-color: #bae6fd;
    background: #f0f9ff;
    color: #075985;
  }

  .toast-icon {
    font-size: 1.1rem;
  }
</style>
