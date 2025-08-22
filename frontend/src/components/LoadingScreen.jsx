import React, { useRef, useState } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { Sparkles, ArrowLeft } from 'lucide-react';
import { Button } from './ui/button';

const LoadingScreen = ({ onCancel, query = "" }) => {
  const containerRef = useRef(null);
  const textRef = useRef(null);
  const cursorRef = useRef(null);
  const spinnerRef = useRef(null);
  const [displayText, setDisplayText] = useState('');

  // Comprehensive loading messages for long-running tasks
  const loadingMessages = [
    "🔍 Searching latest studies...",
    "📚 Analyzing research papers...",
    "🧠 Extracting key insights...",
    "⚡ Processing abstracts...",
    "🔬 Reviewing methodologies...",
    "📊 Comparing results across studies...",
    "🎯 Identifying patterns...",
    "📈 Synthesizing findings...",
    "🧩 Connecting research dots...",
    "📋 Organizing evidence...",
    "🔎 Deep-diving into citations...",
    "💡 Generating insights...",
    "📝 Crafting synthesis...",
    "🎨 Polishing final report...",
    "✨ Almost ready...",
    "🚀 Finalizing results...",
    "🎯 Cross-referencing sources...",
    "📑 Validating conclusions...",
    "🔍 Fact-checking details...",
    "🧠 Remembering key facts from the data...",
    "📊 Statistical analysis in progress...",
    "🔬 Examining experimental designs...",
    "📈 Tracking research trends...",
    "🎭 Filtering for quality...",
    "🏗️ Building knowledge map...",
    "🔗 Linking related concepts...",
    "📚 Scanning academic databases...",
    "🎯 Targeting relevant findings...",
    "⚖️ Weighing evidence strength...",
    "🧪 Processing clinical data..."
  ];

  // Typewriter animation for loading messages
  useGSAP(() => {
    if (!textRef.current || !cursorRef.current) return;

    const tl = gsap.timeline({ repeat: -1 });

    loadingMessages.forEach((message, index) => {
      tl.call(() => {
        setDisplayText('');
      })
      .to({}, {
        duration: message.length * 0.04, // Slightly faster for loading
        ease: "none",
        onUpdate: function() {
          const progress = this.progress();
          const charIndex = Math.floor(progress * message.length);
          setDisplayText(message.substring(0, charIndex));
        }
      })
      // Brief pause to read
      .to(cursorRef.current, {
        opacity: 0,
        duration: 0.4,
        repeat: 3,
        yoyo: true,
        ease: "power2.inOut"
      })
      // Quick delete
      .to({}, {
        duration: message.length * 0.015,
        ease: "power2.in", 
        onUpdate: function() {
          const progress = 1 - this.progress();
          const charIndex = Math.floor(progress * message.length);
          setDisplayText(message.substring(0, charIndex));
        }
      })
      .set(cursorRef.current, { opacity: 1 });
    });

    return () => tl.kill();
  }, []);

  // Spinner rotation animation
  useGSAP(() => {
    if (!spinnerRef.current) return;
    
    gsap.to(spinnerRef.current, {
      rotation: 360,
      duration: 3,
      repeat: -1,
      ease: "none"
    });
  }, []);

  // Container entrance animation
  useGSAP(() => {
    if (!containerRef.current) return;
    
    gsap.fromTo(containerRef.current,
      { opacity: 0, scale: 0.9, y: 20 },
      { opacity: 1, scale: 1, y: 0, duration: 0.6, ease: "back.out(1.7)" }
    );
  }, []);

  // Cursor blink animation
  useGSAP(() => {
    if (!cursorRef.current) return;
    gsap.to(cursorRef.current, {
      opacity: 0,
      duration: 0.8,
      repeat: -1,
      yoyo: true,
      ease: "power2.inOut"
    });
  }, []);

  return (
    <div className="fixed inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-4 pt-safe pb-safe z-50">
      {/* Background effects */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -left-40 w-80 h-80 bg-blue-500/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute -bottom-40 -right-40 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl animate-pulse" />
      </div>

      {/* Main loading container */}
      <div ref={containerRef} className="relative z-10 max-w-md w-full">
        {/* Glassmorphism card */}
        <div className="glassmorphism-dark rounded-2xl p-8 border border-white/15 shadow-2xl backdrop-blur-xl">
          {/* Header with spinner */}
          <div className="flex items-center justify-center mb-6">
            <div 
              ref={spinnerRef}
              className="w-12 h-12 bg-gradient-to-r from-cyan-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg"
            >
              <Sparkles className="w-6 h-6 text-white" />
            </div>
          </div>

          {/* Title */}
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-white mb-2">
              Analyzing Research
            </h2>
            <p className="text-gray-400 text-sm">
              Processing your query: <span className="text-blue-400 italic">"{query}"</span>
            </p>
          </div>

          {/* Animated loading text */}
          <div className="text-center mb-8">
            <div className="bg-slate-800/50 rounded-lg p-4 min-h-[3rem] flex items-center justify-center">
              <div className="inline-flex items-center">
                <span 
                  ref={textRef}
                  className="text-base text-gray-200 font-mono"
                >
                  {displayText}
                </span>
                <span 
                  ref={cursorRef}
                  className="text-base text-cyan-400 font-mono ml-1"
                >
                  |
                </span>
              </div>
            </div>
          </div>

          {/* Progress indicator */}
          <div className="mb-6">
            <div className="flex justify-between text-xs text-gray-400 mb-2">
              <span>Processing...</span>
              <span>This may take 3-5 minutes</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2">
              <div className="bg-gradient-to-r from-cyan-500 to-purple-600 h-2 rounded-full animate-pulse w-1/3"></div>
            </div>
          </div>

          {/* Cancel button */}
          {onCancel && (
            <div className="text-center">
              <Button 
                onClick={onCancel}
                variant="ghost" 
                className="text-gray-400 hover:text-white hover:bg-white/10"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Cancel Search
              </Button>
            </div>
          )}
        </div>

        {/* Floating particles effect */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-4 left-4 w-2 h-2 bg-cyan-400 rounded-full opacity-30 animate-bounce" style={{animationDelay: '0s'}}></div>
          <div className="absolute top-8 right-8 w-1 h-1 bg-purple-400 rounded-full opacity-40 animate-bounce" style={{animationDelay: '1s'}}></div>
          <div className="absolute bottom-12 left-8 w-1.5 h-1.5 bg-blue-400 rounded-full opacity-25 animate-bounce" style={{animationDelay: '2s'}}></div>
          <div className="absolute bottom-4 right-12 w-1 h-1 bg-cyan-300 rounded-full opacity-35 animate-bounce" style={{animationDelay: '0.5s'}}></div>
        </div>
      </div>
    </div>
  );
};

export default LoadingScreen;
