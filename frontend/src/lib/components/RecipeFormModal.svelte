<script>
  import {
    isFormModalOpen,
    editingRecipe,
    loadRecipes,
    loadMetadata,
    showToast,
    activeRecipe,
    currentUser
  } from '../stores';
  import { api } from '../api';

  let isSubmitting = false;
  let uploadingCount = 0;
  let fileInput;

  const MAX_IMAGES = 10;

  // Form State
  let title = '';
  let description = '';
  let prep_time_minutes = 15;
  let cook_time_minutes = 20;
  let servings = 4;
  let difficulty = 'Medium';
  let cuisine = 'Italian';
  let category = 'Main Course';
  let tagsInput = '';
  let images = [''];
  let notes = '';

  // Dynamic lists
  let ingredients = [
    { name: '', amount: 1, unit: 'cup', notes: '' }
  ];

  let instructions = [
    { step_number: 1, instruction: '', tip: '' }
  ];

  // Populate if editing
  $: if ($isFormModalOpen) {
    if ($editingRecipe) {
      const r = $editingRecipe;
      title = r.title || '';
      description = r.description || '';
      prep_time_minutes = r.prep_time_minutes || 15;
      cook_time_minutes = r.cook_time_minutes || 20;
      servings = r.servings || 4;
      difficulty = r.difficulty || 'Medium';
      cuisine = r.cuisine || 'Italian';
      category = r.category || 'Main Course';
      tagsInput = (r.tags || []).join(', ');
      notes = r.notes || '';

      if (r.images && r.images.length > 0) {
        images = [...r.images];
      } else if (r.image_url) {
        images = [r.image_url];
      } else {
        images = [''];
      }

      ingredients = (r.ingredients && r.ingredients.length > 0)
        ? JSON.parse(JSON.stringify(r.ingredients))
        : [{ name: '', amount: 1, unit: '', notes: '' }];

      instructions = (r.instructions && r.instructions.length > 0)
        ? JSON.parse(JSON.stringify(r.instructions))
        : [{ step_number: 1, instruction: '', tip: '' }];
    } else {
      // Reset form
      title = '';
      description = '';
      prep_time_minutes = 15;
      cook_time_minutes = 20;
      servings = 4;
      difficulty = 'Medium';
      cuisine = 'Italian';
      category = 'Main Course';
      tagsInput = '';
      images = [''];
      notes = '';
      ingredients = [{ name: '', amount: 1, unit: '', notes: '' }];
      instructions = [{ step_number: 1, instruction: '', tip: '' }];
    }
  }

  function closeModal() {
    isFormModalOpen.set(false);
    editingRecipe.set(null);
  }

  function addImage() {
    images = [...images, ''];
  }

  function removeImage(index) {
    if (images.length <= 1) {
      images = [''];
      return;
    }
    images = images.filter((_, i) => i !== index);
  }

  function filledImages() {
    return images.filter((url) => typeof url === 'string' && url.trim());
  }

  async function handleFilesSelected(event) {
    const files = Array.from(event.target.files || []);
    event.target.value = '';
    if (files.length === 0) return;

    const room = MAX_IMAGES - filledImages().length - uploadingCount;
    if (room <= 0) {
      showToast(`A recipe can have at most ${MAX_IMAGES} photos`, 'error');
      return;
    }
    if (files.length > room) {
      showToast(`Only the first ${room} photo(s) will be added (max ${MAX_IMAGES})`, 'info');
    }

    await Promise.all(files.slice(0, room).map(async (file) => {
      if (!file.type.startsWith('image/')) {
        showToast(`${file.name} is not an image`, 'error');
        return;
      }
      uploadingCount += 1;
      try {
        const uploaded = await api.uploadImage(file);
        // Fill an empty URL row if there is one, otherwise add a new row
        const emptyIdx = images.findIndex((url) => !url || !url.trim());
        if (emptyIdx >= 0) {
          images[emptyIdx] = uploaded.url;
          images = images;
        } else {
          images = [...images, uploaded.url];
        }
      } catch (err) {
        showToast(`Could not upload ${file.name}: ${err.message}`, 'error');
      } finally {
        uploadingCount -= 1;
      }
    }));
  }

  function makeCoverImage(index) {
    if (index === 0) return;
    const selected = images[index];
    const remaining = images.filter((_, i) => i !== index);
    images = [selected, ...remaining];
  }

  function addIngredient() {
    ingredients = [...ingredients, { name: '', amount: 1, unit: '', notes: '' }];
  }

  function removeIngredient(index) {
    if (ingredients.length <= 1) return;
    ingredients = ingredients.filter((_, i) => i !== index);
  }

  function addStep() {
    instructions = [
      ...instructions,
      { step_number: instructions.length + 1, instruction: '', tip: '' }
    ];
  }

  function removeStep(index) {
    if (instructions.length <= 1) return;
    instructions = instructions
      .filter((_, i) => i !== index)
      .map((step, idx) => ({ ...step, step_number: idx + 1 }));
  }

  async function handleSubmit() {
    if (!title.trim()) {
      showToast('Please enter a recipe title', 'error');
      return;
    }

    const validIngredients = ingredients
      .filter((i) => i.name.trim().length > 0)
      .map((i) => ({
        name: i.name.trim(),
        amount: Number(i.amount) || 1,
        unit: i.unit.trim(),
        notes: i.notes?.trim() || null,
      }));

    if (validIngredients.length === 0) {
      showToast('Please provide at least one valid ingredient', 'error');
      return;
    }

    const validInstructions = instructions
      .filter((s) => s.instruction.trim().length > 0)
      .map((s, idx) => ({
        step_number: idx + 1,
        instruction: s.instruction.trim(),
        tip: s.tip?.trim() || null,
      }));

    if (validInstructions.length === 0) {
      showToast('Please provide at least one instruction step', 'error');
      return;
    }

    const tagsArray = tagsInput
      .split(',')
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);

    const validImages = images
      .map((url) => (typeof url === 'string' ? url.trim() : ''))
      .filter((url) => url.length > 0);

    const payload = {
      title: title.trim(),
      description: description.trim() || 'A delicious culinary creation.',
      prep_time_minutes: Number(prep_time_minutes) || 0,
      cook_time_minutes: Number(cook_time_minutes) || 0,
      servings: Number(servings) || 1,
      difficulty,
      cuisine: cuisine.trim(),
      category: category.trim(),
      tags: tagsArray,
      ingredients: validIngredients,
      instructions: validInstructions,
      images: validImages,
      image_url: validImages.length > 0 ? validImages[0] : null,
      notes: notes.trim() || null,
    };

    if (uploadingCount > 0) {
      showToast('Please wait for photo uploads to finish', 'error');
      return;
    }

    isSubmitting = true;
    try {
      if ($editingRecipe) {
        const updated = await api.updateRecipe($editingRecipe.id, payload);
        showToast('Recipe updated successfully!', 'success');
        activeRecipe.set(updated);
      } else {
        await api.createRecipe(payload);
        showToast('Recipe created successfully!', 'success');
      }
      closeModal();
      await Promise.all([loadRecipes(), loadMetadata()]);
    } catch (err) {
      showToast(err.message || 'Failed to save recipe', 'error');
    } finally {
      isSubmitting = false;
    }
  }
</script>

{#if $isFormModalOpen}
  <div
    class="modal-backdrop"
    on:click={closeModal}
    on:keydown={(e) => e.key === 'Escape' && closeModal()}
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
      <div class="modal-header">
        <h2 class="modal-title">
          {$editingRecipe ? '✏️ Edit Recipe' : '✨ Create New Recipe'}
        </h2>
        <button class="close-btn" on:click={closeModal}>✕</button>
      </div>

      <form class="modal-form" on:submit|preventDefault={handleSubmit}>
        <!-- Core Details -->
        <div class="form-section">
          <h4 class="section-heading">Overview</h4>
          <div class="form-group">
            <label for="recipe-title">Title *</label>
            <input
              id="recipe-title"
              type="text"
              class="form-input"
              placeholder="e.g. Creamy Truffle Pasta"
              bind:value={title}
              required
            />
          </div>

          <div class="form-group">
            <label for="recipe-desc">Short Description</label>
            <textarea
              id="recipe-desc"
              rows="2"
              class="form-textarea"
              placeholder="What makes this dish delicious?"
              bind:value={description}
            ></textarea>
          </div>

          <div class="form-row-4">
            <div class="form-group">
              <label for="recipe-cuisine">Cuisine</label>
              <input id="recipe-cuisine" type="text" class="form-input" bind:value={cuisine} placeholder="Italian" />
            </div>
            <div class="form-group">
              <label for="recipe-category">Category</label>
              <input id="recipe-category" type="text" class="form-input" bind:value={category} placeholder="Main Course" />
            </div>
            <div class="form-group">
              <label for="recipe-diff">Difficulty</label>
              <select id="recipe-diff" class="form-select" bind:value={difficulty}>
                <option value="Easy">Easy</option>
                <option value="Medium">Medium</option>
                <option value="Hard">Hard</option>
              </select>
            </div>
            <div class="form-group">
              <label for="recipe-servings">Servings</label>
              <input id="recipe-servings" type="number" min="1" max="100" class="form-input" bind:value={servings} />
            </div>
          </div>

          <div class="form-row-3">
            <div class="form-group">
              <label for="recipe-prep">Prep Time (mins)</label>
              <input id="recipe-prep" type="number" min="0" class="form-input" bind:value={prep_time_minutes} />
            </div>
            <div class="form-group">
              <label for="recipe-cook">Cook Time (mins)</label>
              <input id="recipe-cook" type="number" min="0" class="form-input" bind:value={cook_time_minutes} />
            </div>
            <div class="form-group">
              <label for="recipe-tags">Tags (comma separated)</label>
              <input id="recipe-tags" type="text" class="form-input" placeholder="quick, vegetarian, pasta" bind:value={tagsInput} />
            </div>
          </div>

        </div>

        <!-- Recipe Photos Section -->
        <div class="form-section">
          <div class="section-title-row">
            <div>
              <h4 class="section-heading">Recipe Photos</h4>
              <p class="section-subtext">Upload photos or add image URLs. The first image serves as the primary cover.</p>
            </div>
            <div class="photo-buttons">
              <input
                bind:this={fileInput}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                multiple
                hidden
                on:change={handleFilesSelected}
              />
              <button
                type="button"
                class="btn btn-primary btn-sm"
                on:click={() => fileInput.click()}
                disabled={uploadingCount > 0}
              >
                {uploadingCount > 0 ? `Uploading ${uploadingCount}…` : '⬆ Upload Photo'}
              </button>
              <button type="button" class="btn btn-outline-primary btn-sm" on:click={addImage}>
                + Add Image URL
              </button>
            </div>
          </div>

          <div class="dynamic-rows">
            {#each images as imgUrl, idx}
              <div class="image-row">
                <div class="image-badge-wrap">
                  {#if idx === 0}
                    <span class="cover-pill" title="Cover photo">★ Cover</span>
                  {:else}
                    <span class="photo-idx">#{idx + 1}</span>
                  {/if}
                </div>

                <div class="image-input-box">
                  {#if imgUrl && imgUrl.startsWith('/')}
                    <span class="uploaded-label" title={imgUrl}>Uploaded photo</span>
                  {:else}
                    <input
                      type="url"
                      class="form-input"
                      placeholder="https://images.unsplash.com/photo-..."
                      bind:value={images[idx]}
                    />
                  {/if}
                  {#if imgUrl && imgUrl.trim()}
                    <img
                      src={imgUrl}
                      alt="Preview {idx + 1}"
                      class="tiny-preview"
                      on:error={(e) => (e.target.style.display = 'none')}
                      on:load={(e) => (e.target.style.display = 'block')}
                    />
                  {/if}
                </div>

                <div class="image-actions">
                  {#if idx > 0}
                    <button
                      type="button"
                      class="btn btn-ghost btn-sm set-cover-btn"
                      on:click={() => makeCoverImage(idx)}
                      title="Set as primary cover photo"
                    >
                      Make Cover
                    </button>
                  {/if}
                  <button
                    type="button"
                    class="remove-row-btn"
                    on:click={() => removeImage(idx)}
                    title="Remove photo"
                    disabled={images.length <= 1 && !images[0]}
                  >
                    ✕
                  </button>
                </div>
              </div>
            {/each}
          </div>
        </div>

        <!-- Ingredients Editor -->
        <div class="form-section">
          <div class="section-title-row">
            <h4 class="section-heading">Ingredients *</h4>
            <button type="button" class="btn btn-outline-primary btn-sm" on:click={addIngredient}>
              + Add Ingredient
            </button>
          </div>

          <div class="dynamic-rows">
            {#each ingredients as ing, idx}
              <div class="ingredient-row">
                <input
                  type="text"
                  placeholder="Ingredient name (e.g. Flour)"
                  class="form-input ing-name-input"
                  bind:value={ing.name}
                  required
                />
                <input
                  type="number"
                  step="any"
                  min="0.01"
                  placeholder="Qty"
                  class="form-input ing-amount-input"
                  bind:value={ing.amount}
                  required
                />
                <input
                  type="text"
                  placeholder="Unit (g, cups, tbsp)"
                  class="form-input ing-unit-input"
                  bind:value={ing.unit}
                />
                <input
                  type="text"
                  placeholder="Notes (diced, cold)"
                  class="form-input ing-notes-input"
                  bind:value={ing.notes}
                />
                <button
                  type="button"
                  class="remove-row-btn"
                  on:click={() => removeIngredient(idx)}
                  disabled={ingredients.length <= 1}
                >✕</button>
              </div>
            {/each}
          </div>
        </div>

        <!-- Instructions Editor -->
        <div class="form-section">
          <div class="section-title-row">
            <h4 class="section-heading">Step-by-Step Instructions *</h4>
            <button type="button" class="btn btn-outline-primary btn-sm" on:click={addStep}>
              + Add Step
            </button>
          </div>

          <div class="dynamic-rows">
            {#each instructions as step, idx}
              <div class="instruction-row">
                <div class="step-num">{idx + 1}</div>
                <div class="step-inputs">
                  <textarea
                    rows="2"
                    class="form-textarea"
                    placeholder="Describe step instruction..."
                    bind:value={step.instruction}
                    required
                  ></textarea>
                  <input
                    type="text"
                    class="form-input tip-input"
                    placeholder="💡 Pro-tip for this step (optional)"
                    bind:value={step.tip}
                  />
                </div>
                <button
                  type="button"
                  class="remove-row-btn"
                  on:click={() => removeStep(idx)}
                  disabled={instructions.length <= 1}
                >✕</button>
              </div>
            {/each}
          </div>
        </div>

        <!-- Optional Chef Notes -->
        <div class="form-section">
          <h4 class="section-heading">Chef's Notes & Advice (Optional)</h4>
          <div class="form-group">
            <label for="chef-notes">Pairing suggestions, storage advice, or culinary variations</label>
            <textarea
              id="chef-notes"
              rows="3"
              class="form-textarea"
              placeholder="e.g. For extra crispy crust, let the dough rest at room temperature. Keeps well for 3 days."
              bind:value={notes}
            ></textarea>
          </div>
        </div>

        <!-- Form Actions -->
        <div class="modal-form-actions">
          <button type="button" class="btn btn-secondary" on:click={closeModal} disabled={isSubmitting}>
            Cancel
          </button>
          <button type="submit" class="btn btn-primary" disabled={isSubmitting || uploadingCount > 0}>
            {isSubmitting ? 'Saving...' : $editingRecipe ? 'Update Recipe' : 'Save Recipe'}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(4px);
    z-index: 60;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
  }

  .modal-card {
    background: var(--bg-surface);
    width: 100%;
    max-width: 850px;
    max-height: 90vh;
    border-radius: var(--radius-xl);
    overflow-y: auto;
    position: relative;
    box-shadow: var(--shadow-xl);
    display: flex;
    flex-direction: column;
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 1.75rem;
    border-bottom: 1px solid var(--border-color);
  }

  .modal-title {
    font-family: var(--font-serif);
    font-size: 1.4rem;
    color: var(--text-main);
  }

  .close-btn {
    background: transparent;
    border: none;
    font-size: 1.25rem;
    cursor: pointer;
    color: var(--text-muted);
  }

  .modal-form {
    padding: 1.5rem 1.75rem;
    display: flex;
    flex-direction: column;
    gap: 1.75rem;
  }

  .form-section {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid var(--border-subtle);
  }

  .section-heading {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-main);
  }

  .section-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .form-group label {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-muted);
  }

  .form-row-4 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
  }

  .form-row-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.75rem;
  }

  .section-subtext {
    font-size: 0.78rem;
    color: var(--text-muted);
    margin-top: 0.15rem;
  }

  .image-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: var(--bg-subtle);
    padding: 0.55rem 0.85rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-color);
  }

  .image-badge-wrap {
    min-width: 65px;
    display: flex;
    align-items: center;
  }

  .cover-pill {
    background: #fef3c7;
    color: #92400e;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 0.2rem 0.55rem;
    border-radius: 9999px;
    white-space: nowrap;
    border: 1px solid #fde68a;
  }

  .photo-idx {
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--text-muted);
    padding-left: 0.35rem;
  }

  .image-input-box {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .photo-buttons {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .uploaded-label {
    flex: 1;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-muted);
    padding: 0.5rem 0.25rem;
  }

  .tiny-preview {
    width: 42px;
    height: 42px;
    border-radius: var(--radius-sm);
    object-fit: cover;
    border: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .image-actions {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .set-cover-btn {
    font-size: 0.78rem;
    color: var(--primary);
    padding: 0.3rem 0.55rem;
  }

  .set-cover-btn:hover {
    background: var(--primary-light);
  }

  .dynamic-rows {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .ingredient-row {
    display: grid;
    grid-template-columns: 2.5fr 1fr 1fr 2fr 34px;
    gap: 0.5rem;
    align-items: center;
  }

  .instruction-row {
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .step-num {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--bg-subtle);
    border: 1px solid var(--border-color);
    font-size: 0.85rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 0.4rem;
    flex-shrink: 0;
  }

  .step-inputs {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .tip-input {
    font-size: 0.82rem;
    background: #fffbeb;
    border-color: #fde68a;
  }

  .remove-row-btn {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
    background: white;
    color: #ef4444;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    transition: all 0.15s ease;
  }

  .remove-row-btn:hover:not(:disabled) {
    background: #fee2e2;
  }

  .remove-row-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .modal-form-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.75rem;
    padding-top: 1rem;
  }

  @media (max-width: 768px) {
    .form-row-4, .form-row-3 {
      grid-template-columns: 1fr 1fr;
    }
    .ingredient-row {
      grid-template-columns: 1fr 1fr;
    }
  }
</style>
