import React from 'react';
import SearchPage from './components/SearchPage';
import './App.css';

function App() {
  return (
    <>
      {/* Skip link for keyboard users */}
      <a href="#main-content" className="skip-link sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:bg-black focus:text-white focus:px-3 focus:py-2 focus:rounded">
        Skip to main content
      </a>
      <main id="main-content" role="main" className="min-h-svh">
        <SearchPage />
      </main>
    </>
  );
}

export default App;
