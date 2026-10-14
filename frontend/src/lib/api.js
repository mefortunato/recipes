// API Client for FastAPI backend
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('recipe_access_token') : null;
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, { ...options, headers });
    if (response.status === 204) {
      return null;
    }
    const data = await response.json();
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

export const api = {
  // Authentication & Permissions
  async getAuthConfig() {
    return request('/auth/config');
  },

  async verifyGoogleCredential(credential) {
    const data = await request('/auth/google/verify', {
      method: 'POST',
      body: JSON.stringify({ credential }),
    });
    if (data?.access_token && typeof localStorage !== 'undefined') {
      localStorage.setItem('recipe_access_token', data.access_token);
    }
    return data;
  },

  async demoLogin(asEditor = true) {
    const data = await request(`/auth/demo-login?as_editor=${asEditor}`, {
      method: 'POST',
    });
    if (data?.access_token && typeof localStorage !== 'undefined') {
      localStorage.setItem('recipe_access_token', data.access_token);
    }
    return data;
  },

  async getMe() {
    return request('/auth/me');
  },

  async logout() {
    try {
      await request('/auth/logout', { method: 'POST' });
    } finally {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('recipe_access_token');
      }
    }
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
    if (params.page) query.set('page', params.page);
    if (params.page_size) query.set('page_size', params.page_size);

    const queryString = query.toString() ? `?${query.toString()}` : '';
    return request(`/recipes${queryString}`);
  },

  async getRecipe(id) {
    return request(`/recipes/${id}`);
  },

  async createRecipe(recipeData) {
    return request('/recipes', {
      method: 'POST',
      body: JSON.stringify(recipeData),
    });
  },

  async updateRecipe(id, recipeData) {
    return request(`/recipes/${id}`, {
      method: 'PUT',
      body: JSON.stringify(recipeData),
    });
  },

  async deleteRecipe(id) {
    return request(`/recipes/${id}`, {
      method: 'DELETE',
    });
  },

  async scaleRecipe(id, servings) {
    return request(`/recipes/${id}/scale?servings=${servings}`);
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
