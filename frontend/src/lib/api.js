// API Client for FastAPI backend
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// Sessions live in the backend's httpOnly cookie, out of reach of page scripts.
// Older builds also kept the JWT in localStorage; remove any copy left behind.
try {
  localStorage.removeItem('recipe_access_token');
} catch {
  // Storage unavailable (private mode, blocked site data): nothing to clean up
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, { ...options, headers, credentials: 'include' });
    if (response.status === 204) {
      return null;
    }
    const isJson = response.headers.get('content-type')?.includes('application/json');
    const data = isJson ? await response.json() : null;
    if (!response.ok) {
      const errorMsg = data?.detail?.message || data?.detail || 'An unexpected error occurred';
      throw new Error(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
    }
    return data;
  } catch (err) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

// Phone photos can be 10+ MB. Shrink big ones in the browser first so uploads are quick;
// the server still validates, resizes and re-encodes everything it stores.
const CLIENT_RESIZE_THRESHOLD_BYTES = 2 * 1024 * 1024;
const CLIENT_MAX_DIMENSION = 2400;

async function shrinkForUpload(file) {
  if (file.size <= CLIENT_RESIZE_THRESHOLD_BYTES || typeof createImageBitmap !== 'function') {
    return file;
  }
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
    const scale = Math.min(1, CLIENT_MAX_DIMENSION / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close?.();
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9));
    return blob && blob.size < file.size ? blob : file;
  } catch {
    // Browser can't decode it (e.g. HEIC on desktop): let the server decide
    return file;
  }
}

export const api = {
  // Authentication & Permissions
  async getAuthConfig() {
    return request('/auth/config');
  },

  async verifyGoogleCredential(credentialOrPayload) {
    const payload = typeof credentialOrPayload === 'string'
      ? { credential: credentialOrPayload }
      : credentialOrPayload;
    return request('/auth/google/verify', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async getMe() {
    return request('/auth/me');
  },

  // Admin & User Permissions Management
  async getAdminUsers(params = {}) {
    const query = new URLSearchParams();
    if (params.search) query.set('search', params.search);
    if (params.role && params.role !== 'All') query.set('role', params.role);
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return request(`/admin/users${queryString}`);
  },

  async updateUserPermissions(userId, permissions) {
    return request(`/admin/users/${encodeURIComponent(userId)}/permissions`, {
      method: 'PATCH',
      body: JSON.stringify(permissions),
    });
  },

  async provisionUser(userData) {
    return request('/admin/users', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  },

  async deleteUser(userId) {
    return request(`/admin/users/${encodeURIComponent(userId)}`, {
      method: 'DELETE',
    });
  },

  async logout() {
    return request('/auth/logout', { method: 'POST' });
  },

  async logoutAll() {
    return request('/auth/logout-all', { method: 'POST' });
  },

  async revokeUserSessions(userId) {
    return request(`/admin/users/${encodeURIComponent(userId)}/revoke-sessions`, { method: 'POST' });
  },

  // Recipes
  async getRecipes(params = {}) {
    const query = new URLSearchParams();
    if (params.search) query.set('search', params.search);
    if (params.category && params.category !== 'All') query.set('category', params.category);
    if (params.cuisine && params.cuisine !== 'All') query.set('cuisine', params.cuisine);
    if (params.tag) query.set('tag', params.tag);
    if (params.max_time) query.set('max_time', params.max_time);
    if (params.difficulty && params.difficulty !== 'All') query.set('difficulty', params.difficulty);
    if (params.is_favorite !== undefined && params.is_favorite !== null) query.set('is_favorite', params.is_favorite);
    if (params.user_voted) query.set('user_voted', params.user_voted);
    if (params.sort_by) query.set('sort_by', params.sort_by);
    if (params.sort_order !== undefined && params.sort_order !== null) query.set('sort_order', params.sort_order);
    if (params.page) query.set('page', params.page);
    if (params.page_size) query.set('page_size', params.page_size);

    const queryString = query.toString() ? `?${query.toString()}` : '';
    return request(`/recipes${queryString}`);
  },

  async getRecipe(id) {
    return request(`/recipes/${encodeURIComponent(id)}`);
  },

  async voteRecipe(id, vote, toggle = false) {
    return request(`/recipes/${encodeURIComponent(id)}/vote`, {
      method: 'POST',
      body: JSON.stringify({ vote, toggle }),
    });
  },

  async upvoteRecipe(id) {
    return request(`/recipes/${encodeURIComponent(id)}/upvote`, {
      method: 'POST',
    });
  },

  async downvoteRecipe(id) {
    return request(`/recipes/${encodeURIComponent(id)}/downvote`, {
      method: 'POST',
    });
  },

  async clearRecipeVote(id) {
    return request(`/recipes/${encodeURIComponent(id)}/vote`, {
      method: 'DELETE',
    });
  },

  async createRecipe(recipeData) {
    return request('/recipes', {
      method: 'POST',
      body: JSON.stringify(recipeData),
    });
  },

  async updateRecipe(id, recipeData) {
    return request(`/recipes/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(recipeData),
    });
  },

  // Upload a photo; resolves to { id, url, width, height, size_bytes, ... }
  async uploadImage(file) {
    const body = new FormData();
    const prepared = await shrinkForUpload(file);
    body.append('file', prepared, file.name || 'photo.jpg');
    // No Content-Type header: the browser sets the multipart boundary itself
    const response = await fetch(`${API_BASE}/images`, { method: 'POST', body, credentials: 'include' });
    const isJson = response.headers.get('content-type')?.includes('application/json');
    const data = isJson ? await response.json() : null;
    if (!response.ok) {
      const detail = data?.detail;
      const message = typeof detail === 'string'
        ? detail
        : response.status === 413
          ? 'Image is too large to upload.'
          : 'Image upload failed.';
      throw new Error(message);
    }
    return data;
  },

  async deleteRecipe(id) {
    return request(`/recipes/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
  },

  async scaleRecipe(id, servings) {
    return request(`/recipes/${encodeURIComponent(id)}/scale?servings=${encodeURIComponent(servings)}`);
  },

  // Metadata
  async getTags() {
    return request('/recipes/meta/tags');
  },

  async getCuisines() {
    return request('/recipes/meta/cuisines');
  },

  async getCategories() {
    return request('/recipes/meta/categories');
  },

  async seedRecipes(force = false) {
    return request(`/recipes/seed?force=${force}`, {
      method: 'POST',
    });
  },

  // Health
  async checkHealth() {
    try {
      const res = await fetch('/health/ready');
      if (!res.ok) return { status: 'unhealthy' };
      return await res.json();
    } catch {
      return { status: 'offline' };
    }
  },
};
