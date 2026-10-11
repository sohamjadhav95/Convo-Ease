// Entry point: restore the session, then show sign-in or the app.
import { api, onUnauthenticated } from './api.js';
import { store, on, navigate } from './store.js';
import { mountAuth } from './auth.js';
import { mountShell, unmountShell } from './shell.js';
import { snackbar } from './ui.js';

const root = document.getElementById('app');
let signedIn = false;

function showApp(user) {
  store.user = user;
  signedIn = true;
  if (!location.hash || location.hash === '#' || location.hash === '#/') navigate('chats', { replace: true });
  mountShell(root);
}

function showAuth(message) {
  signedIn = false;
  unmountShell();
  store.user = null;
  store.groups = [];
  store.groupsLoaded = false;
  document.querySelectorAll('dialog').forEach((d) => d.remove());
  mountAuth(root, (user) => showApp(user));
  if (message) snackbar(message);
}

onUnauthenticated(() => {
  if (signedIn) showAuth('Your session ended. Please sign in again.');
});
on('signed-out', () => showAuth('Signed out'));

async function boot() {
  const [me, settings] = await Promise.all([api.me(), api.settings()]);
  if (settings.success) store.settings = settings.settings;
  if (me.success && me.user) showApp(me.user);
  else showAuth();
}

boot();
