import React, { useEffect, useRef, useState } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { Search, Key, Sparkles, Settings, ChevronDown, X, Check, Zap, BookOpen, Beaker, Database } from 'lucide-react';
import ResultsPage from './ResultsPage';
import AnimatedExamples from './AnimatedExamples';
import LoadingScreen from './LoadingScreen';
import { debounce } from 'lodash-es';
import { useCallback } from 'react';

const SearchPage = () => {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [searchDepth, setSearchDepth] = useState('low');
  const [selectedModel, setSelectedModel] = useState('gpt-5-mini');
  const [allowedDepths, setAllowedDepths] = useState(['low', 'med']);
  const [selectedSources, setSelectedSources] = useState(['arxiv', 'pubmed', 'openalex']);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(-1);
  const [examples, setExamples] = useState([
    'AlphaFold limits in membrane proteins?',
    'Bias in climate ensemble forecasts?',
    'Single-cell RNA: batch effects best fix?',
    'Graph transformers for drug design?',
    'Causal RL for healthcare triage?',
    'LLMs for synthesis: hallucination guards?',
    'Cryo-EM map denoising with diffusion?',
    'Protein language models vs structures?',
    'Quantum error mitigation near term?',
    'Genome editing off-target prediction?',
    'Multimodal fusion for radiology?',
    'Meta-analysis: small-study bias fixes?',
    'Human-in-the-loop active learning gains?',
    'Counterfactuals for policy evaluation?',
    'Self-supervised pretraining for EHRs?',
    'Robustness of RCTs vs observational?',
    'Efficient retrieval for long contexts?',
    'Scalable Bayesian inference tricks?',
    'Fairness metrics under distribution shift?',
    'Weak supervision for labeling at scale?'
  ]);
  const abortControllerRef = useRef(null);

  // Popular research topics for suggestions
  const popularTopics = [
    "machine learning in healthcare",
    "climate change mitigation strategies",
    "CRISPR gene editing applications",
    "quantum computing breakthroughs",
    "renewable energy technologies",
    "artificial intelligence ethics",
    "cancer immunotherapy advances",
    "sustainable agriculture methods"
  ];

  const getApiBase = () => (process.env.REACT_APP_API_URL || '').replace(/\/+$/, '');

  const containerRef = useRef(null);
  const titleRef = useRef(null);
  const searchRef = useRef(null);
  const inputRef = useRef(null);
  const buttonRef = useRef(null);

  // Initial animations
  useGSAP(() => {
    const tl = gsap.timeline();
    tl.fromTo(titleRef.current, { opacity: 0, y: 20 }, { opacity: 1, y: 0, duration: 0.8, ease: 'power3.out' })
      .fromTo(searchRef.current, { opacity: 0, scale: 0.95 }, { opacity: 1, scale: 1, duration: 0.6, ease: 'power2.out' }, '-=0.4');
  }, { scope: containerRef });



  // Load saved preferences
  useEffect(() => {
    try {
      const savedKey = localStorage.getItem('user_api_key');
      if (savedKey) setApiKey(savedKey);
      const savedDepth = localStorage.getItem('search_depth');
      if (savedDepth && ['low', 'med', 'high'].includes(savedDepth)) setSearchDepth(savedDepth);
      const savedModel = localStorage.getItem('model_name');
      if (savedModel) setSelectedModel(savedModel);
      const savedSources = localStorage.getItem('selected_sources');
      if (savedSources) {
        try {
          const sources = JSON.parse(savedSources);
          if (Array.isArray(sources) && sources.length > 0) {
            setSelectedSources(sources);
          }
        } catch {}
      }
    } catch {}
  }, []);

  // Fetch examples from backend
  useEffect(() => {
    const fetchExamples = async () => {
      try {
        const apiBase = getApiBase();
        const res = await fetch(`${apiBase}/examples`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.examples) && data.examples.length > 0) {
            setExamples(data.examples);
          }
        }
      } catch (error) {
        console.log('Failed to fetch examples, using defaults:', error);
        // Keep the default examples if fetch fails
      }
    };
    fetchExamples();
  }, []);

  // Fetch allowed depths from backend
  useEffect(() => {
    const fetchLimits = async () => {
      try {
        const apiBase = getApiBase();
        const res = await fetch(`${apiBase}/limits`, { headers: { ...(apiKey ? { 'X-User-Api-Key': apiKey } : {}) } });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.allowed_depths)) setAllowedDepths(data.allowed_depths);
        }
      } catch {}
    };
    fetchLimits();
  }, [apiKey]);

  // Suggestion filtering logic
  const debouncedUpdateSuggestions = useCallback(
    debounce((query) => {
      if (query.length > 2) {
        const filtered = popularTopics.filter(topic =>
          topic.toLowerCase().includes(query.toLowerCase())
        );
        setSuggestions(filtered.slice(0, 5));
        setShowSuggestions(filtered.length > 0);
      } else {
        setShowSuggestions(false);
      }
    }, 300),
    [popularTopics]
  );

  useEffect(() => {
    debouncedUpdateSuggestions(query);
    return () => debouncedUpdateSuggestions.cancel();
  }, [query, debouncedUpdateSuggestions]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // Create new abort controller for this request
    abortControllerRef.current = new AbortController();
    
    setIsSearching(true);
    setError(null);
    gsap.to(buttonRef.current, { scale: 0.95, duration: 0.1, yoyo: true, repeat: 1 });
    
    try {
      const apiBase = process.env.REACT_APP_API_URL || '';
      const response = await fetch(`${apiBase}/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(apiKey ? { 'X-User-Api-Key': apiKey } : {}) },
        body: JSON.stringify({ 
          query: query.trim(), 
          max_results: depthToMax(searchDepth), 
          model: selectedModel,
          sources: selectedSources
        }),
        signal: abortControllerRef.current.signal
      });
      if (response.status === 202) {
        const queued = await response.json().catch(() => ({}));
        const taskId = queued.task_id;
        if (!taskId) throw new Error('Failed to enqueue job');
        const result = await pollTaskUntilDone(apiBase, taskId, apiKey);
        if (result && result.result) { setResults(result.result); setError(null); }
        else if (result && result.error) { throw new Error(result.error); }
        else { throw new Error('Job did not complete'); }
        return;
      }
      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || `Request failed with ${response.status}`);
      }
      const data = await response.json();
      setResults(data);
      setError(null);
    } catch (e) {
      // Don't show error if request was aborted
      if (e.name === 'AbortError') {
        return;
      }
      setError(e.message || 'Something went wrong. Please try again.');
    } finally {
      setIsSearching(false);
      abortControllerRef.current = null;
    }
  };

  const pollTaskUntilDone = async (apiBase, taskId, key) => {
    const maxAttempts = 180;
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        const res = await fetch(`${apiBase}/research/${taskId}`, { headers: { ...(key ? { 'X-User-Api-Key': key } : {}) } });
        const data = await res.json().catch(() => ({}));
        if (data.status === 'success') return data;
        if (data.status === 'failure') return data;
      } catch {}
      const delay = 1000 + Math.min(2000, attempt * 20);
      await new Promise((r) => setTimeout(r, delay));
    }
    return { error: 'Timed out waiting for job result' };
  };

  const depthToMax = (depth) => {
    switch (depth) {
      case 'med': return 5;
      case 'high': return 10;
      case 'low':
      default: return 3;
    }
  };

  const depthConfig = {
    low: { label: 'Quick', papers: '3 papers', icon: Zap, color: 'text-green-400' },
    med: { label: 'Standard', papers: '5 papers', icon: BookOpen, color: 'text-blue-400' },
    high: { label: 'Deep', papers: '10 papers', icon: Beaker, color: 'text-purple-400' }
  };

  const models = [
    { id: 'gpt-5-mini', name: 'GPT-5 Mini', badge: 'Fast' },
    { id: 'gpt-5', name: 'GPT-5', badge: 'Balanced' },
    { id: 'o3-mini', name: 'O3 Mini', badge: 'Efficient' },
    { id: 'o3', name: 'O3', badge: 'Advanced' },
    { id: 'o3-pro', name: 'O3 Pro', badge: 'Premium', requiresKey: true }
  ];

  const sources = [
    { id: 'arxiv', name: 'arXiv', description: 'Physics, Math, CS, Biology', icon: '📚' },
    { id: 'pubmed', name: 'PubMed', description: 'Biomedical & Life Sciences', icon: '🏥' },
    { id: 'openalex', name: 'OpenAlex', description: 'Multidisciplinary Research', icon: '🔬' }
  ];

  const toggleSource = (sourceId) => {
    const newSources = selectedSources.includes(sourceId)
      ? selectedSources.filter(s => s !== sourceId)
      : [...selectedSources, sourceId];
    
    // Ensure at least one source is selected
    if (newSources.length === 0) return;
    
    setSelectedSources(newSources);
    try {
      localStorage.setItem('selected_sources', JSON.stringify(newSources));
    } catch {}
  };

  // Enhanced keyboard navigation
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (activeSuggestionIndex >= 0 && suggestions[activeSuggestionIndex]) {
        setQuery(suggestions[activeSuggestionIndex]);
        setShowSuggestions(false);
      } else {
        handleSearch();
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveSuggestionIndex(prev =>
        prev < suggestions.length - 1 ? prev + 1 : prev
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveSuggestionIndex(prev => prev > -1 ? prev - 1 : -1);
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setActiveSuggestionIndex(-1);
    }
  };

  // Show loading screen when searching
  if (isSearching) {
    return (
      <LoadingScreen 
        query={query}
        onCancel={() => {
          if (abortControllerRef.current) {
            abortControllerRef.current.abort();
          }
          setIsSearching(false);
          setError(null); // Don't show error for user cancellation
        }}
      />
    );
  }

  // Show results page if we have results
  if (results) {
    return <ResultsPage results={results} onBack={() => { setResults(null); setQuery(''); }} />;
  }

  return (
    <div ref={containerRef} className="min-h-svh bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      {/* Animated background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-80 h-80 bg-blue-500/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute -bottom-40 -right-40 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl animate-pulse" />
      </div>

      <div className="relative z-10 flex flex-col items-center justify-center min-h-svh p-4 pt-safe pb-safe">
        {/* Header */}
        <div ref={titleRef} className="text-center mb-12">
          <div className="inline-flex items-center gap-2 mb-4 px-3 py-1 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-full border border-white/10">
            <Sparkles className="w-4 h-4 text-blue-400" />
            <span className="text-xs font-medium text-gray-300">AI-Powered Research</span>
          </div>
          <h1 className="text-5xl md:text-6xl font-bold text-white mb-3">
            Brilliance <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">2.1</span>
          </h1>
          <p className="text-gray-400 max-w-md mx-auto">Discover and synthesize academic research with advanced AI</p>
        </div>

        {/* Search Container */}
        {/* Animated examples above the search box */}
        <AnimatedExamples examples={examples} isVisible={!query} />
        <div ref={searchRef} className="w-full max-w-2xl">
          <div className="relative group" role="search" aria-label="Research search">
            <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500/50 to-purple-500/50 rounded-2xl blur opacity-30 group-hover:opacity-50 transition duration-500" />
            <div className="relative bg-slate-900/90 backdrop-blur-xl rounded-2xl border border-white/10 p-2">
              <div className="flex items-center gap-2">
                <div className="flex-1 relative">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="w-full h-14 bg-transparent text-white pl-12 pr-4 focus:outline-none focus:ring-2 focus:ring-blue-500/50 text-lg placeholder:text-gray-500 transition-all duration-200"
                    placeholder={query ? "" : "Ask me anything..."}
                    aria-label="Search query"
                    autoComplete="off"
                    autoCorrect="off"
                    autoCapitalize="none"
                    spellCheck="false"
                    inputMode="search"
                    enterKeyHint="search"
                    maxLength="500"
                    aria-describedby="search-help"
                    role="combobox"
                    aria-expanded={showSuggestions}
                    aria-autocomplete="list"
                    aria-activedescendant={activeSuggestionIndex >= 0 ? `suggestion-${activeSuggestionIndex}` : undefined}
                  />
                  {/* Add character counter for long queries */}
                  {query.length > 400 && (
                    <div className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-gray-500">
                      {query.length}/500
                    </div>
                  )}
                </div>
                <button
                  ref={buttonRef}
                  onClick={handleSearch}
                  disabled={isSearching || !query.trim()}
                  className={`h-14 px-6 font-medium rounded-xl transition-all duration-200 shadow-lg relative overflow-hidden ${
                    isSearching || !query.trim()
                      ? 'bg-gray-600 cursor-not-allowed opacity-50'
                      : 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 hover:shadow-xl hover:scale-105 active:scale-95'
                  }`}
                  aria-label="Search"
                  aria-busy={isSearching}
                >
                  {isSearching ? (
                    <div className="flex items-center gap-2">
                      <div className="relative">
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      </div>
                      <span>Searching...</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <Search className="w-4 h-4" />
                      <span>Search</span>
                    </div>
                  )}
                </button>
              </div>

               {/* Quick Settings Bar */}
               <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 px-4 py-2 border-t border-white/5 mt-2">
                 <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => setShowSettings(!showSettings)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-white/5 hover:bg-white/10 text-gray-300 rounded-lg transition-colors"
                    aria-expanded={showSettings}
                    aria-controls="settings-panel"
                    aria-haspopup="true"
                  >
                    <Settings className="w-3.5 h-3.5" />
                    <span>Settings</span>
                    <ChevronDown className={`w-3 h-3 transition-transform ${showSettings ? 'rotate-180' : ''}`} />
                  </button>
                  <button
                    onClick={() => setShowKeyModal(true)}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-white/5 hover:bg-white/10 text-gray-300 rounded-lg transition-colors"
                  >
                    <Key className="w-3.5 h-3.5" />
                    <span>{apiKey ? 'API Key Set' : 'Add API Key'}</span>
                  </button>
                </div>
                 <div className="flex items-center gap-2 text-xs text-gray-400 mt-1 sm:mt-0">
                  <span className="px-2 py-1 bg-white/5 rounded">{selectedModel}</span>
                  <span className={`px-2 py-1 bg-white/5 rounded ${depthConfig[searchDepth].color}`}>{depthConfig[searchDepth].label}</span>
                  <span className="px-2 py-1 bg-white/5 rounded text-emerald-400">{selectedSources.length} source{selectedSources.length !== 1 ? 's' : ''}</span>
                </div>
              </div>
            </div>
            <div id="search-help" className="sr-only">
              Enter your research question and press Enter or click Search to find relevant academic papers
            </div>
          </div>

          {/* Settings Panel */}
          {showSettings && (
            <div id="settings-panel" className="mt-4 p-6 bg-slate-900/90 backdrop-blur-xl rounded-2xl border border-white/10 animate-in slide-in-from-top-2 duration-300" role="region" aria-label="Search settings">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Search Settings</h3>
                <span className="text-xs text-gray-400 bg-white/5 px-2 py-1 rounded">Configure your search</span>
              </div>

              <div className="grid lg:grid-cols-3 md:grid-cols-2 gap-6">
                {/* Search Depth with better descriptions */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">Search Depth</label>
                    <p className="text-xs text-gray-400 mb-3">More papers provide deeper insights but take longer</p>
                  </div>
                  <div className="space-y-2">
                    {Object.entries(depthConfig).map(([key, config]) => {
                      const Icon = config.icon;
                      const disabled = !allowedDepths.includes(key);
                      return (
                        <button
                          key={key}
                          onClick={() => { if (!disabled) { setSearchDepth(key); try { localStorage.setItem('search_depth', key); } catch {} } }}
                          disabled={disabled}
                          className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all group ${
                            searchDepth === key
                              ? 'bg-blue-500/10 border-blue-500/30 ring-1 ring-blue-500/20'
                              : disabled
                              ? 'bg-white/5 border-white/5 opacity-50 cursor-not-allowed'
                              : 'bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20'
                          }`}
                          aria-pressed={searchDepth === key}
                        >
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${searchDepth === key ? 'bg-blue-500/20' : 'bg-white/10'}`}>
                              <Icon className={`w-4 h-4 ${config.color}`} aria-hidden="true" />
                            </div>
                            <div className="text-left">
                              <div className="text-sm font-medium text-white">{config.label}</div>
                              <div className="text-xs text-gray-400">{config.papers} • {key === 'low' ? '~30s' : key === 'med' ? '~60s' : '~120s'}</div>
                            </div>
                          </div>
                          {searchDepth === key && (
                            <div className="flex items-center gap-2">
                              <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
                              <Check className="w-4 h-4 text-blue-400" aria-hidden="true" />
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Model Selection with better badges */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">AI Model</label>
                    <p className="text-xs text-gray-400 mb-3">Choose the right model for your needs</p>
                  </div>
                  <div className="space-y-2">
                    {models.map((model) => (
                      <button
                        key={model.id}
                        onClick={() => { if (!model.requiresKey || apiKey) { setSelectedModel(model.id); try { localStorage.setItem('model_name', model.id); } catch {} } }}
                        disabled={model.requiresKey && !apiKey}
                        className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all ${
                          selectedModel === model.id
                            ? 'bg-purple-500/10 border-purple-500/30 ring-1 ring-purple-500/20'
                            : model.requiresKey && !apiKey
                            ? 'bg-white/5 border-white/5 opacity-50 cursor-not-allowed'
                            : 'bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20'
                        }`}
                        aria-pressed={selectedModel === model.id}
                      >
                        <div className="text-left">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-white">{model.name}</span>
                            {model.requiresKey && (
                              <span className="text-xs bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full border border-amber-500/30">
                                Premium
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-gray-400 mt-1">{model.badge}</div>
                        </div>
                        {selectedModel === model.id && <Check className="w-4 h-4 text-purple-400" aria-hidden="true" />}
                      </button>
                    ))}
                  </div>
                </div>

                {/* API Sources Selection */}
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-1">API Sources</label>
                    <p className="text-xs text-gray-400 mb-3">Choose which databases to search</p>
                  </div>
                  <div className="space-y-2">
                    {sources.map((source) => (
                      <button
                        key={source.id}
                        onClick={() => toggleSource(source.id)}
                        className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all ${
                          selectedSources.includes(source.id)
                            ? 'bg-emerald-500/10 border-emerald-500/30 ring-1 ring-emerald-500/20'
                            : 'bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/20'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-lg ${selectedSources.includes(source.id) ? 'bg-emerald-500/20' : 'bg-white/10'}`}>
                            <span className="text-lg" aria-hidden="true">{source.icon}</span>
                          </div>
                          <div className="text-left">
                            <div className="text-sm font-medium text-white">{source.name}</div>
                            <div className="text-xs text-gray-400">{source.description}</div>
                          </div>
                        </div>
                        {selectedSources.includes(source.id) && (
                          <Check className="w-4 h-4 text-emerald-400" aria-hidden="true" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Add quick reset button */}
              <div className="mt-6 pt-4 border-t border-white/10">
                <button
                  onClick={() => {
                    setSearchDepth('low');
                    setSelectedModel('gpt-5-mini');
                    setSelectedSources(['arxiv', 'pubmed', 'openalex']);
                    try {
                      localStorage.setItem('search_depth', 'low');
                      localStorage.setItem('model_name', 'gpt-5-mini');
                      localStorage.setItem('selected_sources', JSON.stringify(['arxiv', 'pubmed', 'openalex']));
                    } catch {}
                  }}
                  className="text-xs text-gray-400 hover:text-gray-300 transition-colors"
                >
                  Reset to defaults
                </button>
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl backdrop-blur-sm animate-in slide-in-from-top-2" role="alert">
              <div className="flex items-start gap-3">
                <div className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0">
                  <svg viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-red-400 font-medium">Search failed</p>
                  <p className="text-xs text-red-300/80 mt-1">{error}</p>
                  <button
                    onClick={() => setError(null)}
                    className="text-xs text-red-300 hover:text-red-200 mt-2 underline underline-offset-2"
                  >
                    Try again
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="mt-12 text-center text-xs text-gray-500">
          <p>Free tier limits apply. Add API key to unlock premium models.</p>
        </div>

        {/* Add suggestions dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-slate-800/95 backdrop-blur-xl rounded-xl border border-white/10 shadow-2xl z-50 overflow-auto max-h-[50svh]">
            {suggestions.map((suggestion, index) => (
              <button
                key={suggestion}
                onClick={() => {
                  setQuery(suggestion);
                  setShowSuggestions(false);
                  setActiveSuggestionIndex(-1);
                }}
                className={`w-full text-left px-4 py-3 text-sm transition-colors ${
                  index === activeSuggestionIndex
                    ? 'bg-blue-500/20 text-blue-300'
                    : 'text-gray-300 hover:bg-white/5'
                }`}
              >
                <Search className="w-4 h-4 inline mr-2 opacity-50" />
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* API Key Modal */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md bg-slate-900 rounded-2xl border border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">API Key Configuration</h3>
              <button onClick={() => setShowKeyModal(false)} className="p-1 hover:bg-white/10 rounded-lg transition-colors" aria-label="Close API key modal">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <p className="text-sm text-gray-400 mb-4">Your API key is stored locally and used for authentication.</p>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key"
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-white/20"
              aria-label="Enter API key"
            />
            <div className="flex gap-3 mt-6">
              <button onClick={() => setShowKeyModal(false)} className="flex-1 px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors">Cancel</button>
              <button onClick={() => { try { localStorage.setItem('user_api_key', apiKey); } catch {} setShowKeyModal(false); }} className="flex-1 px-4 py-2 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white rounded-lg transition-all">Save Key</button>
            </div>
          </div>
        </div>
      )}

      {/* Add skip link at the top */}
      <a href="#main-search" className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 bg-blue-600 text-white px-4 py-2 rounded-lg z-50">
        Skip to search
      </a>

      {/* Add keyboard shortcuts hint */}
      <div className="mt-8 text-center mb-safe">
        <p className="text-xs text-gray-500">
          <kbd className="px-2 py-1 bg-white/10 rounded text-xs">Enter</kbd> to search •
          <kbd className="px-2 py-1 bg-white/10 rounded text-xs ml-2">↑↓</kbd> to navigate suggestions
        </p>
      </div>
    </div>
  );
};

export default SearchPage;

