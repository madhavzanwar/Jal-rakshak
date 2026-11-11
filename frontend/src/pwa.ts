/** Registers the Workbox service worker in production builds only. */
export async function registerPwa(): Promise<void> {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return;
  const { registerSW } = await import('virtual:pwa-register');
  registerSW({ immediate: true });
}
