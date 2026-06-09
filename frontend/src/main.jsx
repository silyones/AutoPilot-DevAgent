import React from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';

const rootEl = document.getElementById('root');
if (!rootEl) {
  console.error('Root element #root not found');
} else {
  try {
    createRoot(rootEl).render(
      <React.StrictMode>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </React.StrictMode>,
    );
  } catch (err) {
    console.error('Failed to mount React app:', err);
    rootEl.textContent = 'Failed to load the UI. Please refresh the page.';
  }
}
