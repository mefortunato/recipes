<script>
  import { isApiKeysModalOpen, showToast } from '../stores';
  import { api } from '../api';

  const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

  let keys = [];
  let loading = false;
  let newKeyName = 'Recipe co-author agent';
  let creating = false;
  let createdKey = null; // { key, name, ... } shown once, right after creation
  let revokingId = null;

  $: guideUrl = typeof window !== 'undefined'
    ? new URL(`${API_BASE}/agents/guide`, window.location.origin).href
    : `${API_BASE}/agents/guide`;

  $: agentPrompt = createdKey
    ? `When I tell you I like a recipe we've worked on, save it to my Gourmet Vault recipe book.\n` +
      `Instructions for the API: ${guideUrl}\n` +
      `My API key (send it as "Authorization: Bearer <key>"): ${createdKey.key}`
    : '';

  $: if ($isApiKeysModalOpen) {
    loadKeys();
  }

  function closeModal() {
    isApiKeysModalOpen.set(false);
    createdKey = null;
  }

  async function loadKeys() {
    loading = true;
    try {
      keys = (await api.listApiKeys()).keys;
    } catch (err) {
      showToast(err.message || 'Could not load your API keys.', 'error');
    } finally {
      loading = false;
    }
  }

  async function createKey() {
    if (creating || !newKeyName.trim()) return;
    creating = true;
    try {
      createdKey = await api.createApiKey(newKeyName.trim());
      newKeyName = 'Recipe co-author agent';
      await loadKeys();
    } catch (err) {
      showToast(err.message || 'Could not create the API key.', 'error');
    } finally {
      creating = false;
    }
  }

  async function revokeKey(key) {
    if (!confirm(`Revoke "${key.name}"? Agents using it will stop being able to save recipes.`)) return;
    revokingId = key.id;
    try {
      await api.revokeApiKey(key.id);
      if (createdKey?.id === key.id) createdKey = null;
      keys = keys.filter((k) => k.id !== key.id);
      showToast('API key revoked.', 'info');
    } catch (err) {
      showToast(err.message || 'Could not revoke the API key.', 'error');
    } finally {
      revokingId = null;
    }
  }

  async function copy(text, label) {
    try {
      await navigator.clipboard.writeText(text);
      showToast(`${label} copied to the clipboard.`, 'success');
    } catch {
      showToast('Copy failed; select the text and copy it by hand.', 'error');
    }
  }

  function formatDate(value) {
    if (!value) return 'Never';
    // MongoDB hands back naive UTC timestamps; mark them as UTC before parsing
    const date = new Date(/(Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`);
    return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  }
</script>

{#if $isApiKeysModalOpen}
  <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
  <div
    class="modal-backdrop"
    on:click={closeModal}
    on:keydown={(e) => e.key === 'Escape' && closeModal()}
    role="presentation"
  >
    <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
    <div
      class="keys-card animate-fade-in"
      on:click|stopPropagation
      on:keydown|stopPropagation
      role="dialog"
      aria-modal="true"
      aria-labelledby="api-keys-title"
      tabindex="-1"
    >
      <div class="keys-header">
        <div>
          <h2 id="api-keys-title" class="keys-title">🤖 Agent API Keys</h2>
          <p class="keys-subtitle">
            Let an AI agent you co-write recipes with save the ones you like straight into your book.
            A key can add and edit recipes and upload photos as you. It can't delete recipes or manage users.
          </p>
        </div>
        <button class="close-btn" on:click={closeModal} aria-label="Close">✕</button>
      </div>

      <div class="keys-body">
        {#if createdKey}
          <section class="created-panel">
            <h3>Your new key: copy it now</h3>
            <p class="hint">This is the only time it's shown. If you lose it, revoke it and create another.</p>
            <div class="secret-row">
              <code class="secret">{createdKey.key}</code>
              <button class="btn btn-secondary btn-sm" on:click={() => copy(createdKey.key, 'API key')}>Copy key</button>
            </div>

            <h3>Give your agent these instructions</h3>
            <p class="hint">
              Paste this into the agent's instructions (for example a Claude project or custom instructions).
              Anything you paste into a chat is kept in that conversation, so prefer a place you control, and
              revoke the key if it ends up somewhere it shouldn't.
            </p>
            <textarea class="prompt" readonly rows="5" value={agentPrompt}></textarea>
            <div class="prompt-actions">
              <button class="btn btn-primary btn-sm" on:click={() => copy(agentPrompt, 'Agent instructions')}>Copy instructions</button>
              <a class="btn btn-ghost btn-sm" href={guideUrl} target="_blank" rel="noopener noreferrer">Preview the agent guide</a>
            </div>
          </section>
        {/if}

        <form class="create-row" on:submit|preventDefault={createKey}>
          <label class="sr-only" for="new-key-name">Key name</label>
          <input
            id="new-key-name"
            class="name-input"
            bind:value={newKeyName}
            maxlength="80"
            placeholder="Name, e.g. Claude recipe co-author"
          />
          <button class="btn btn-primary btn-sm" type="submit" disabled={creating || !newKeyName.trim()}>
            {creating ? 'Creating…' : 'Create key'}
          </button>
        </form>

        {#if loading && keys.length === 0}
          <p class="hint">Loading…</p>
        {:else if keys.length === 0}
          <p class="hint">You have no API keys yet.</p>
        {:else}
          <ul class="key-list">
            {#each keys as key (key.id)}
              <li class="key-item">
                <div class="key-info">
                  <span class="key-name">{key.name}</span>
                  <span class="key-meta">
                    <code>{key.prefix}…</code> · created {formatDate(key.created_at)} · last used {formatDate(key.last_used_at)}
                  </span>
                </div>
                <button
                  class="btn btn-danger btn-sm"
                  disabled={revokingId === key.id}
                  on:click={() => revokeKey(key)}
                >
                  {revokingId === key.id ? 'Revoking…' : 'Revoke'}
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(28, 25, 23, 0.55);
    backdrop-filter: blur(6px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1rem;
  }

  .keys-card {
    background: var(--bg-surface);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-xl);
    width: 100%;
    max-width: 680px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .keys-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--border-color);
  }

  .keys-title {
    font-family: var(--font-serif);
    font-size: 1.35rem;
    margin-bottom: 0.25rem;
  }

  .keys-subtitle,
  .hint {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .close-btn {
    background: transparent;
    border: none;
    font-size: 1.15rem;
    color: var(--text-muted);
    cursor: pointer;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .close-btn:hover {
    background: var(--bg-subtle);
  }

  .keys-body {
    padding: 1.25rem 1.5rem 1.5rem;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .created-panel {
    background: var(--primary-light);
    border: 1px solid var(--primary-glow);
    border-radius: var(--radius-md);
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .created-panel h3 {
    font-size: 0.95rem;
    margin-top: 0.25rem;
  }

  .secret-row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .secret {
    flex: 1;
    min-width: 0;
    overflow-wrap: anywhere;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    padding: 0.45rem 0.6rem;
    font-size: 0.82rem;
  }

  .prompt {
    width: 100%;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.8rem;
    padding: 0.6rem;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    background: var(--bg-surface);
    color: var(--text-main);
    resize: vertical;
  }

  .prompt-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .create-row {
    display: flex;
    gap: 0.5rem;
  }

  .name-input {
    flex: 1;
    min-width: 0;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    font: inherit;
    font-size: 0.9rem;
  }

  .name-input:focus {
    outline: 2px solid var(--primary-glow);
    border-color: var(--primary);
  }

  .key-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .key-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
    padding: 0.7rem 0.85rem;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }

  .key-info {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .key-name {
    font-weight: 600;
    font-size: 0.92rem;
  }

  .key-meta {
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
  }
</style>
