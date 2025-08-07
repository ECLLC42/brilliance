import React, { useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { Button } from './ui/button';

const ResultsPage = ({ results, onBack }) => {
  const containerRef = useRef(null);
  const contentRef = useRef(null);

  useGSAP(() => {
    // Fade in animation
    gsap.fromTo(contentRef.current,
      { opacity: 0, y: 30 },
      { opacity: 1, y: 0, duration: 0.8, ease: "power2.out" }
    );
  }, { scope: containerRef });

  if (!results || !results.synthesis) {
    return (
      <div ref={containerRef} className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
        <div ref={contentRef} className="text-center">
          <div className="text-6xl mb-4">🤔</div>
          <h2 className="text-2xl font-bold text-white mb-2">No Results Found</h2>
          <p className="text-gray-400 mb-6">Try a different search query</p>
          <Button onClick={onBack} className="bg-gradient-to-r from-cyan-500 to-purple-600 hover:from-cyan-600 hover:to-purple-700">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Search
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4">
      {/* Background effects */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-cyan-500 rounded-full mix-blend-multiply filter blur-xl opacity-20 animate-pulse delay-1000"></div>
      </div>

      {/* Header */}
      <div className="relative z-10 max-w-4xl mx-auto mb-8">
        <Button 
          onClick={onBack}
          variant="ghost" 
          className="text-white hover:bg-white/10 mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Search
        </Button>
        
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-xl flex items-center justify-center">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">Research Synthesis</h1>
            <p className="text-gray-400">AI-powered analysis of your research query</p>
          </div>
        </div>
      </div>

      {/* Results Container */}
      <div ref={contentRef} className="relative z-10 max-w-4xl mx-auto">
        <div className="glassmorphism-dark rounded-3xl p-8 backdrop-blur-xl border border-white/10 shadow-2xl">
          <div className="prose prose-invert max-w-none">
            <div className="text-lg leading-relaxed text-gray-200 whitespace-pre-wrap">
              {results.synthesis}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResultsPage; 