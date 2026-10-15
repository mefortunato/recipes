import { writable, get } from 'svelte/store';
import { api } from './api';

export const recipes = writable([]);
export const totalRecipes = writable(0);
export const currentPage = writable(1);
export const totalPages = writable(1);
export const loading = writable(false);

export const filters = writable({
  search: '',
  category: 'All',
  cuisine: 'All',
  difficulty: 'All',
  max_time: null,
  is_favorite: null,
  tag: null,
});

export const tags = writable([]);
export const cuisines = writable([]);
export const categories = writable([]);

export const activeRecipe = writable(null);
export const isViewModalOpen = writable(false);

export const isFormModalOpen = writable(false);
export const editingRecipe = writable(null);

// Authentication & Access Control stores
export const currentUser = writable(null);
export const authConfig = writable(null);
export const isAuthModalOpen = writable(false);
export const isAdminModalOpen = writable(false);
export const authLoading = writable(true);

export const toast = writable({
  show: false,
  message: '',
  type: 'info', // 'success', 'error', 'info'
});

export const systemHealth = writable({
  status: 'checking',
  database: 'unknown',
  latency_ms: null,
});

export function showToast(message, type = 'info', duration = 3500) {
  toast.set({ show: true, message, type });
  setTimeout(() => {
    toast.update((t) => ({ ...t, show: false }));
  }, duration);
}

export async function initAuth() {
  authLoading.set(true);

  // Check URL parameters from OAuth callback redirect
  if (typeof window !== 'undefined') {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('auth_success')) {
      showToast('Signed in with Google successfully! 🎉', 'success');
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (urlParams.get('error') === 'oauth_failed') {
      showToast('Google Sign-In was cancelled or failed.', 'error');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  try {
    const config = await api.getAuthConfig();
    authConfig.set(config);
  } catch (err) {
    console.warn('Failed to load auth config:', err);
  }

  try {
    const user = await api.getMe();
    currentUser.set(user);
  } catch (err) {
    currentUser.set(null);
  } finally {
    authLoading.set(false);
  }
}

export async function handleLogout() {
  try {
    await api.logout();
    currentUser.set(null);
    showToast('Signed out successfully.', 'info');
  } catch (err) {
    showToast('Error during logout.', 'error');
  }
}

export async function loadRecipes() {
  loading.set(true);
  try {
    const currentFilters = get(filters);
    const page = get(currentPage);
    const res = await api.getRecipes({ ...currentFilters, page });
    recipes.set(res.recipes);
    totalRecipes.set(res.total);
    totalPages.set(res.total_pages);
  } catch (err) {
    showToast(err.message || 'Failed to fetch recipes', 'error');
  } finally {
    loading.set(false);
  }
}

export async function loadMetadata() {
  try {
    const [t, c, cat] = await Promise.all([
      api.getTags(),
      api.getCuisines(),
      api.getCategories(),
    ]);
    tags.set(t);
    cuisines.set(c);
    categories.set(cat);
  } catch (err) {
    console.warn('Failed to load recipe metadata:', err);
  }
}

export async function checkBackendHealth() {
  try {
    const res = await api.checkHealth();
    if (res.status === 'ready') {
      systemHealth.set({
        status: 'online',
        database: res.database?.status || 'connected',
        latency_ms: res.database?.latency_ms || 0,
      });
    } else {
      systemHealth.set({
        status: res.status || 'degraded',
        database: 'unreachable',
        latency_ms: null,
      });
    }
  } catch {
    systemHealth.set({
      status: 'offline',
      database: 'disconnected',
      latency_ms: null,
    });
  }
}
