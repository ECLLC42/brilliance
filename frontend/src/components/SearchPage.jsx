import React, { useRef, useState } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Search, Sparkles, Zap } from 'lucide-react';
import ResultsPage from './ResultsPage';

const SearchPage = () => {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState(null);
  const containerRef = useRef(null);
  const titleRef = useRef(null);
  const searchContainerRef = useRef(null);
  const inputRef = useRef(null);
  const buttonRef = useRef(null);

  useGSAP(() => {
    // Initial animation sequence
    const tl = gsap.timeline();
    
    tl.fromTo(titleRef.current, 
      { opacity: 0, y: -50 },
      { opacity: 1, y: 0, duration: 1, ease: "power3.out" }
    )
    .fromTo(searchContainerRef.current,
      { opacity: 0, y: 30, scale: 0.9 },
      { opacity: 1, y: 0, scale: 1, duration: 0.8, ease: "back.out(1.7)" },
      "-=0.5"
    )
    .fromTo(inputRef.current,
      { opacity: 0, x: -20 },
      { opacity: 1, x: 0, duration: 0.6, ease: "power2.out" },
      "-=0.3"
    )
    .fromTo(buttonRef.current,
      { opacity: 0, x: 20 },
      { opacity: 1, x: 0, duration: 0.6, ease: "power2.out" },
      "-=0.3"
    );

    // Floating animation for the search container
    gsap.to(searchContainerRef.current, {
      y: -5,
      duration: 2,
      ease: "power2.inOut",
      yoyo: true,
      repeat: -1
    });

  }, { scope: containerRef });

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
      const response = await fetch('/research', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: query.trim() })
      });

      const data = await response.json();
      console.log('Search results:', data);
      setResults(data);
      
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setIsSearching(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const handleBackToSearch = () => {
    setResults(null);
    setQuery('');
  };

  // Show results page if we have results
  if (results) {
    return <ResultsPage results={results} onBack={handleBackToSearch} />;
  }

  return (
    <div 
      ref={containerRef}
      className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex flex-col items-center justify-center p-4"
    >
      {/* Background effects */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-cyan-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse delay-1000"></div>
      </div>

      {/* Main content */}
      <div className="relative z-10 w-full max-w-4xl mx-auto text-center">
        {/* Title */}
        <div ref={titleRef} className="mb-12">
          <h1 className="text-6xl md:text-7xl font-bold bg-gradient-to-r from-white via-cyan-300 to-purple-300 bg-clip-text text-transparent mb-4">
            Brilliance 2.0
          </h1>
          <p className="text-xl text-gray-300 max-w-2xl mx-auto">
            Advanced research assistant powered by AI synthesis
          </p>
        </div>

        {/* Search Container */}
        <div 
          ref={searchContainerRef}
          className="relative max-w-2xl mx-auto"
        >
          <div className="flex items-center gap-4">
            {/* Search input */}
            <textarea
              ref={inputRef}
              rows={1}
              placeholder="Ask anything about research, science, or discovery..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                // auto-resize
                e.target.style.height = "auto";
                e.target.style.height = `${e.target.scrollHeight}px`;
              }}
              onKeyPress={handleKeyPress}
              className="flex-grow min-h-[4rem] max-h-40 text-lg bg-white/10 backdrop-blur-md border-white/20 text-white placeholder:text-gray-400 rounded-2xl px-6 py-4 focus:ring-2 focus:ring-cyan-400 focus:border-transparent transition-all duration-300 resize-none overflow-hidden"
            />
            
            {/* Search button */}
            <Button
              ref={buttonRef}
              onClick={handleSearch}
              disabled={isSearching || !query.trim()}
              className="h-12 px-6 bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-600 hover:to-purple-700 text-white font-medium rounded-xl transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-cyan-500/25"
            >
              {isSearching ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
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

          {/* Decorative elements */}
          <div className="absolute -top-4 -left-4 w-8 h-8 bg-gradient-to-r from-cyan-400 to-purple-500 rounded-full opacity-60 animate-pulse"></div>
          <div className="absolute -bottom-4 -right-4 w-6 h-6 bg-gradient-to-r from-purple-400 to-cyan-500 rounded-full opacity-60 animate-pulse delay-500"></div>
        </div>

        {/* Features */}
        <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          <div className="text-center group">
            <div className="w-16 h-16 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform duration-300">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">AI Synthesis</h3>
            <p className="text-gray-400">Intelligent analysis and synthesis of research findings</p>
          </div>
          
          <div className="text-center group">
            <div className="w-16 h-16 bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform duration-300">
              <Zap className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Multi-Source</h3>
            <p className="text-gray-400">Search across PubMed, arXiv, and OpenAlex simultaneously</p>
          </div>
          
          <div className="text-center group">
            <div className="w-16 h-16 bg-gradient-to-r from-green-500 to-teal-500 rounded-2xl flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform duration-300">
              <Search className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Smart Search</h3>
            <p className="text-gray-400">Query optimization for better research results</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SearchPage; 