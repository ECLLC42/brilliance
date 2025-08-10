import React, { useEffect, useRef, useState } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { Button } from './ui/button';
// Removed cmdk Command.Input in favor of native form semantics
import { Search, Key, ListFilter } from 'lucide-react';
import ResultsPage from './ResultsPage';

const SearchPage = () => {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [needsKey, setNeedsKey] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [showDepthModal, setShowDepthModal] = useState(false);
  const [searchDepth, setSearchDepth] = useState('low'); // 'low' | 'med' | 'high'
  const [allowedDepths, setAllowedDepths] = useState(['low','med']);
  const [selectedModel, setSelectedModel] = useState('gpt-5-mini');
  const [showModelMenu, setShowModelMenu] = useState(false);
  const getApiBase = () => (process.env.REACT_APP_API_URL || '').replace(/\/+$/, '');
  const examples = [
    'protein folding breakthroughs',
    'climate model comparisons',
    'single-cell RNA-seq analysis trends',
    'largest Alzheimer’s 2024 trials',
    'best foundation models for biology',
  ];
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const containerRef = useRef(null);
  const titleRef = useRef(null);
  const searchContainerRef = useRef(null);
  const inputRef = useRef(null);
  const buttonRef = useRef(null);

  useGSAP(() => {
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) return;

    const tl = gsap.timeline();
    
    tl.fromTo(titleRef.current, 
      { opacity: 0, y: -30 },
      { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }
    )
    .fromTo(searchContainerRef.current,
      { opacity: 0, y: 16, scale: 0.98 },
      { opacity: 1, y: 0, scale: 1, duration: 0.5, ease: "power2.out" },
      "-=0.3"
    )
    .fromTo(inputRef.current,
      { opacity: 0, x: -12 },
      { opacity: 1, x: 0, duration: 0.4, ease: "power2.out" },
      "-=0.2"
    )
    .fromTo(buttonRef.current,
      { opacity: 0, x: 12 },
      { opacity: 1, x: 0, duration: 0.4, ease: "power2.out" },
      "-=0.2"
    );


    // Subtle micro-motion (single yoyo), no infinite loop
    gsap.to(searchContainerRef.current, {
      y: -2,
      duration: 2,
      ease: "power2.inOut",
      yoyo: true,
      repeat: 1
    });

  }, { scope: containerRef });

  // Rotate placeholder every 2s when input is empty
  useEffect(() => {
    if (query.trim().length > 0) return;
    const id = setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % examples.length);
    }, 2000);
    return () => clearInterval(id);
  }, [query, examples.length]);

  // Load any saved API key on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem('user_api_key');
      if (saved) setApiKey(saved);
      const savedDepth = localStorage.getItem('search_depth');
      if (savedDepth && ['low','med','high'].includes(savedDepth)) setSearchDepth(savedDepth);
      const savedModel = localStorage.getItem('model_name');
      if (savedModel && ['o3','o3-mini','gpt-5','gpt-5-mini','o3-pro'].includes(savedModel)) setSelectedModel(savedModel);
    } catch {}
  }, []);

  // Fetch allowed depths from backend
  useEffect(() => {
    const fetchLimits = async () => {
      try {
        const apiBase = getApiBase();
        const res = await fetch(`${apiBase}/limits`, {
          headers: { ...(apiKey ? { 'X-User-Api-Key': apiKey } : {}) }
        });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.allowed_depths)) {
            setAllowedDepths(data.allowed_depths);
          }
          // If backend requires a key and none is stored, prompt immediately
          if (data && data.require_api_key && !(localStorage.getItem('user_api_key') || '').trim()) {
            setShowKeyModal(true);
          }
        }
      } catch {}
    };
    fetchLimits();
  }, [apiKey]);

  const refreshLimitsWithKey = async (key) => {
    try {
      const apiBase = getApiBase();
      const res = await fetch(`${apiBase}/limits`, {
        headers: { ...(key ? { 'X-User-Api-Key': key } : {}) }
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.allowed_depths)) {
          setAllowedDepths(data.allowed_depths);
        }
      }
    } catch {}
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    setIsSearching(true);
    
    // Animate the search button
    gsap.to(buttonRef.current, {
      scale: 0.95,
      duration: 0.1,
      yoyo: true,
      repeat: 1
    });

    try {
      const apiBase = process.env.REACT_APP_API_URL || '';
      const response = await fetch(`${apiBase}/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(apiKey ? { 'X-User-Api-Key': apiKey } : {})
        },
        body: JSON.stringify({ query: query.trim(), max_results: depthToMax(searchDepth), model: selectedModel })
      });

      if (!response.ok) {
        if (response.status === 402) {
          setNeedsKey(true);
          const err = await response.json().catch(() => ({}));
          throw new Error(err.message || 'Free limit reached. Add API key to continue.');
        }
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || `Request failed with ${response.status}`);
      }

      const data = await response.json();
      setResults(data);
      setError(null);
      
    } catch (error) {
      console.error('Search error:', error);
      setError(error.message || 'Something went wrong');
    } finally {
      setIsSearching(false);
    }
  };

  const depthToMax = (depth) => {
    switch (depth) {
      case 'med': return 5;
      case 'high': return 10;
      case 'low':
      default: return 3;
    }
  };

  const handleSaveKey = async () => {
    const trimmed = (apiKey || '').trim();
    if (!trimmed) {
      setError('Please enter a valid API key.');
      return;
    }
    try {
      setSavingKey(true);
      localStorage.setItem('user_api_key', trimmed);
      // ensure state is the saved value (and trigger effects if changed)
      setApiKey(trimmed);
      await refreshLimitsWithKey(trimmed);
      setNeedsKey(false);
      setShowKeyModal(false);
      setError(null);
      // Retry the last search automatically if a query exists
      if (query.trim()) {
        await handleSearch();
      }
    } catch (e) {
      setError('Failed to save key locally.');
    } finally {
      setSavingKey(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const handleBackToSearch = () => {
    setResults(null);
    setQuery('');
  };

  const openKeyModal = () => {
    setShowKeyModal(true);
    setNeedsKey(false);
  };
  const closeKeyModal = () => setShowKeyModal(false);
  const openDepthModal = () => setShowDepthModal(true);
  const closeDepthModal = () => setShowDepthModal(false);
  const handleSaveDepth = (value) => {
    setSearchDepth(value);
    try { localStorage.setItem('search_depth', value); } catch {}
    closeDepthModal();
  };
  const depthLabel = () => (searchDepth === 'med' ? 'Med' : searchDepth === 'high' ? 'High' : 'Low');

  const modelChoices = ['o3','o3-mini','gpt-5','gpt-5-mini','o3-pro'];
  const saveModel = (m) => {
    // If user tries to select o3-pro without a key, ignore
    if (m === 'o3-pro' && !(apiKey && apiKey.trim())) return;
    setSelectedModel(m);
    try { localStorage.setItem('model_name', m); } catch {}
    setShowModelMenu(false);
  };

  // Show results page if we have results
  if (results) {
    return <ResultsPage results={results} onBack={handleBackToSearch} />;
  }
  
    return (
    <>
    <div 
      ref={containerRef}
      className="min-h-screen bg-dark-gradient flex flex-col items-center justify-start p-4 pt-20 md:pt-28"
    >
      {/* Background effects */}
      <div className="bg-waves" aria-hidden="true">
        <div className="wave wave--1" />
        <div className="wave wave--2" />
      </div>
      <div className="bg-streaks" aria-hidden="true">
        <div className="streak streak--tl" />
        <div className="streak streak--br" />
      </div>

      {/* Main content */}
      <div className="relative z-10 w-full max-w-4xl mx-auto text-center">
        {/* API key action moved into the input group for immediate access */}
        {/* Title */}
        <div ref={titleRef} className="mb-8 md:mb-10">
          <h1 className="text-6xl md:text-7xl font-extrabold tracking-tight text-white mb-3">
            Brilliance 2.1 Beta
          </h1>
          <p className="text-base md:text-lg text-gray-300 max-w-2xl mx-auto">
            Advanced research assistant powered by <span className="bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent font-semibold">AI Synthesis</span>
          </p>
        </div>

        {/* Search Container */}
        <div 
          ref={searchContainerRef}
          className="relative max-w-2xl mx-auto glassmorphism-dark rounded-2xl border border-white/10 p-4 md:p-6"
        >
          <form className="flex items-center" onSubmit={(e) => { e.preventDefault(); handleSearch(); }}>
            <label htmlFor="query" className="sr-only">Search query</label>
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-cyan-300/80" />
              <input
                id="query"
                type="search"
                ref={inputRef}
                placeholder={examples[placeholderIdx]}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full h-16 rounded-2xl bg-transparent text-lg text-white placeholder:text-gray-400 border border-white/10 pl-12 pr-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
              />
              {/* Submit button docked to the right inside the field */}
              <Button
                type="submit"
                ref={buttonRef}
                disabled={isSearching || !query.trim()}
                aria-busy={isSearching}
                aria-live="polite"
                className="absolute right-2 top-1/2 -translate-y-1/2 h-12 px-6 bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-600 hover:to-purple-700 text-white font-medium rounded-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-cyan-500/25"
              >
                {isSearching ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Searching...</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <Search className="w-5 h-5" />
                    <span>Search</span>
                  </div>
                )}
              </Button>
            </div>
          </form>
          {/* Bottom-left controls group */}
          <div className="absolute left-3 bottom-3 flex items-center gap-2">
            <button
              type="button"
              onClick={openKeyModal}
              aria-label="Set API key"
              className="h-6 w-6 grid place-items-center rounded-lg bg-white/10 hover:bg-white/20 text-white border border-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
            >
              <Key className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={openDepthModal}
              aria-label="Set number of resources searched"
              className="h-6 w-6 grid place-items-center rounded-lg bg-white/10 hover:bg-white/20 text-white border border-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60"
              title={`Depth: ${searchDepth}`}
            >
              <ListFilter className="w-4 h-4" />
            </button>
            <span className="text-[10px] leading-none px-2 py-1 rounded-md bg-white/8 border border-white/10 text-gray-200 select-none" aria-label={`Current depth ${depthLabel()}`}>{depthLabel()}</span>
          </div>

          {/* Bottom-right model switcher */}
          <div className="absolute right-3 bottom-3 flex items-center gap-2 text-white">
            <span className="text-[10px] uppercase tracking-wide text-gray-300">Model</span>
            <button
              type="button"
              onClick={() => setShowModelMenu((s) => !s)}
              className="text-[10px] leading-none px-2 py-1 rounded-md bg-white/8 border border-white/10 hover:bg-white/20"
              aria-haspopup="menu"
              aria-expanded={showModelMenu}
            >{selectedModel}</button>
            {showModelMenu && (
              <div className="absolute right-0 bottom-10 w-56 rounded-md bg-zinc-900 border border-white/10 shadow-lg p-1 text-left z-50">
                {modelChoices.map((m) => {
                  const isO3Pro = m === 'o3-pro';
                  const disabled = isO3Pro && !(apiKey && apiKey.trim());
                  const label = disabled ? 'o3-pro (API Key Only)' : m;
                  return (
                    <button
                      key={m}
                      onClick={() => { if (!disabled) saveModel(m); }}
                      disabled={disabled}
                      aria-disabled={disabled}
                      title={disabled ? 'Requires API key' : undefined}
                      className={`w-full text-left px-2 py-1 rounded-md text-sm ${selectedModel===m ? 'bg-white/15' : 'hover:bg-white/10'} ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
                    >{label}</button>
                  );
                })}
              </div>
            )}
          </div>

          {/* API key prompt when needed */}
          {needsKey && (
            <div className="mt-4 p-3 rounded-lg bg-white/5 border border-white/10 text-left">
              <div className="text-sm text-gray-200 mb-2">Free limit reached. Enter your API key to continue.</div>
              <div className="flex items-center gap-2">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Paste your API key"
                  className="flex-1 h-10 bg-transparent border border-white/15 rounded-lg px-3 text-white placeholder:text-gray-400 focus:outline-none"
                />
                <Button onClick={handleSaveKey} disabled={savingKey} className="h-10 px-4">
                  {savingKey ? 'Saving…' : 'Save & Retry'}
                </Button>
              </div>
              <div className="text-xs text-gray-400 mt-2">Key is stored locally in your browser and sent only with requests.</div>
            </div>
          )}

          {/* Live error region present in DOM on load */}
          <div id="error-messages" role="alert" aria-atomic="true" className="mt-3 min-h-[1rem] text-sm text-red-300">
            {error}
          </div>

          {/* Decorative corner dots removed for a cleaner silhouette */}
        </div>

        {/* Features */}
        {/* Features section removed per feedback */}
      </div>

      {/* Scroll prompt removed per feedback */}
    </div>
    {/* Modal for API key */}
    <KeyModal
      open={showKeyModal}
      apiKey={apiKey}
      setApiKey={setApiKey}
      onClose={closeKeyModal}
      onSave={handleSaveKey}
      saving={savingKey}
    />
    <DepthModal
      open={showDepthModal}
      value={searchDepth}
      onClose={closeDepthModal}
      onSave={handleSaveDepth}
      allowedDepths={allowedDepths}
    />
    {/* Footer notice: free tier / API key */}
    <div className="fixed inset-x-0 bottom-2 z-50 flex justify-center px-3">
      <div className="text-[11px] md:text-xs text-gray-200 bg-black/50 border border-white/10 rounded-md px-3 py-2 backdrop-blur-sm">
        This beta is limited to 2 questions on low/med resource settings. To enable o3-pro, use your API key to start or contact the creator.
      </div>
    </div>
    </>
  );
};
// Simple modal for API Key settings
const KeyModal = ({ open, apiKey, setApiKey, onClose, onSave, saving }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="w-full max-w-md rounded-2xl bg-zinc-900 text-white border border-white/10 p-5 text-left">
        <div className="text-lg font-semibold mb-2">API Key</div>
        <p className="text-sm text-gray-300 mb-3">Paste your API key. It’s stored locally and sent with requests.</p>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="Paste your API key"
          className="w-full h-11 bg-transparent border border-white/15 rounded-lg px-3 text-white placeholder:text-gray-400 focus:outline-none"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="h-10 px-4 rounded-lg bg-white/10 hover:bg-white/20">Cancel</button>
          <button onClick={onSave} disabled={saving} className="h-10 px-4 rounded-lg bg-gradient-to-r from-cyan-500 to-purple-600 disabled:opacity-50">
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
};

// Modal for selecting search depth
const DepthModal = ({ open, value, onClose, onSave, allowedDepths }) => {
  if (!open) return null;
  const Option = ({ opt, label }) => (
    <button
      onClick={() => allowedDepths.includes(opt) && onSave(opt)}
      disabled={!allowedDepths.includes(opt)}
      className={`px-4 py-2 rounded-lg border ${value===opt ? 'bg-cyan-600/30 border-cyan-400/50' : 'bg-white/10 border-white/15'} ${!allowedDepths.includes(opt) ? 'opacity-40 cursor-not-allowed' : 'hover:bg-white/20'} text-white`}
    >{label}</button>
  );
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="w-full max-w-md rounded-2xl bg-zinc-900 text-white border border-white/10 p-5 text-left">
        <div className="text-lg font-semibold mb-2">Number of Resources Searched</div>
        <p className="text-sm text-gray-300 mb-4">Choose how many papers to retrieve per source.</p>
        <div className="flex items-center gap-2">
          <Option opt="low" label="Low" />
          <Option opt="med" label="Med" />
          <Option opt="high" label="High" />
        </div>
        <div className="mt-4 flex justify-end">
          <button onClick={onClose} className="h-10 px-4 rounded-lg bg-white/10 hover:bg-white/20">Close</button>
        </div>
      </div>
    </div>
  );
};

export default SearchPage; 
