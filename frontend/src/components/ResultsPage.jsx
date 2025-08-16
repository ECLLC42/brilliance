import React, { useEffect, useMemo, useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ArrowLeft, Sparkles } from 'lucide-react';
import { Button } from './ui/button';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';

const ResultsPage = ({ results, onBack }) => {
  const containerRef = useRef(null);
  const contentRef = useRef(null);

  useGSAP(() => {
    // Fade in animation
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) return;

    gsap.fromTo(contentRef.current,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.5, ease: "power2.out" }
    );
  }, { scope: containerRef });

  const headingRef = useRef(null);
  useEffect(() => { headingRef.current?.focus(); }, []);

  // Build references from synthesis + enrich with metadata from raw_results
  const { transformedMd, references } = useMemo(() => {
    if (!results || !results.synthesis) {
      return { transformedMd: '', references: [] };
    }
    const md = results.synthesis || '';
    if (!md || typeof md !== 'string') return md;
    try {
      // Build reference key -> URL map from the References section (format: Title — URL)
      const refHeaderMatch = md.match(/(^|\n)References\s*\n/i);
      const refsStart = refHeaderMatch ? refHeaderMatch.index + refHeaderMatch[0].length : -1;
      const refMap = new Map();
      const refIndexMap = new Map();
      const refsArray = [];
      if (refsStart >= 0) {
        const tail = md.slice(refsStart);
        const lines = tail.split(/\n+/);
        let idx = 1;
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          const m = trimmed.match(/^(.*?)\s—\s(https?:\S+|URL unavailable)$/);
          if (m && m[1]) {
            const key = m[1].trim();
            const url = m[2] && m[2] !== 'URL unavailable' ? m[2].trim() : '';
            if (url) {
              refMap.set(key, url);
              refIndexMap.set(key, idx);
              refsArray.push({ index: idx, title: key, url, authors: '', year: '', abstract: '' });
              idx += 1;
            }
          }
        }
      }

      // Remove original References section; we'll render cards for refs
      const bodyOnly = refsStart >= 0 ? md.slice(0, refHeaderMatch.index).trimEnd() : md;

      // Replace inline citations [Short Title, 2025] within body with anchored Cite N pills linked to reference URL
      const linked = bodyOnly.replace(/\[([^\]]+?)\]/g, (full, content) => {
        // Derive short key: take content before the last comma if present
        const parts = content.split(',');
        const shortKey = parts.length > 1 ? parts.slice(0, -1).join(',').trim() : content.trim();
        const url = refMap.get(shortKey);
        const idx = refIndexMap.get(shortKey);
        if (url && idx) {
          // Render pill "Cite N" linked to study
          return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium bg-blue-600 text-white">Cite ${idx}</a>`;
        }
        return full;
      });

      // Render evidence-tier + sample size as bright blue pill tags
      const bluePill = (label) => `<span class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium bg-blue-600 text-white">${label}</span>`;
      const withEvidence = linked.replace(/\((human(?:\s*RCT)?|animal|in vitro)\s*(?:,\s*N\s*=\s*(\d+))?\)/gi, (match, tier, n) => {
        const tag = tier.toLowerCase().includes('human') ? 'human' : tier.toLowerCase();
        const pills = [bluePill(tag)];
        if (n) pills.push(bluePill(`N=${n}`));
        return ` ${pills.join(' ')} `;
      });

      // Enrich references with metadata parsed from raw_results blocks
      try {
        const sources = results.raw_results || {};
        const blocks = [sources.arxiv, sources.pubmed, sources.openalex].filter(Boolean).join('\n\n');
        const chunks = blocks.split(/\n\n+/);
        for (const ref of refsArray) {
          const matchChunk = chunks.find((c) => c && c.startsWith(ref.title + ' '));
          if (matchChunk) {
            const lines = matchChunk.split('\n');
            const first = lines[0] || '';
            // Title (Year) by Authors
            const yearMatch = first.match(/\((\d{4})\)/);
            ref.year = yearMatch ? yearMatch[1] : '';
            const byIdx = first.toLowerCase().indexOf(' by ');
            if (byIdx >= 0) ref.authors = first.slice(byIdx + 4).trim();
            const absLine = lines.find((l) => l.startsWith('Abstract: '));
            if (absLine) {
              const abs = absLine.replace('Abstract: ', '').trim();
              const words = abs.split(/\s+/).slice(0, 60).join(' ');
              ref.abstract = words + (abs.length > words.length ? '…' : '');
            }
          }
        }
      } catch {}

      // Return only transformed body to avoid duplication
      return { transformedMd: withEvidence, references: refsArray };
    } catch {
      return { transformedMd: md, references: [] };
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results.synthesis, results.raw_results]);

  if (!results || !results.synthesis) {
    return (
      <div ref={containerRef} className="min-h-svh bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4 pb-safe">
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
    <div ref={containerRef} className="min-h-svh bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4 pt-safe pb-safe">
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
            <h1 ref={headingRef} tabIndex="-1" className="text-3xl font-bold text-white">Research Synthesis</h1>
            <p className="text-gray-400">AI-powered analysis of your research query</p>
          </div>
        </div>
      </div>

      {/* Results Container */}
      <div ref={contentRef} className="relative z-10 max-w-4xl mx-auto">
        <div className="glassmorphism-dark rounded-2xl p-8 md:p-10 border border-white/15 shadow-xl">
          <div className="prose prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={{
              a: ({node, ...props}) => (
                <a {...props} className={(props.className ? props.className + ' ' : '') + 'text-blue-400 underline hover:text-blue-300'} />
              )
            }}>
              {transformedMd}
            </ReactMarkdown>
          </div>
        </div>

        {/* References as cards */}
        {references && references.length > 0 && (
          <div className="mt-6 grid gap-4">
            <div className="text-sm text-gray-300">References</div>
            {references.map((ref) => (
              <button
                key={ref.index}
                onClick={() => { if (ref.url) window.open(ref.url, '_blank', 'noopener'); }}
                className="w-full text-left p-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium bg-blue-600 text-white shrink-0">Cite {ref.index}</span>
                  <div className="flex-1">
                    <div className="text-white font-medium mb-1">{ref.title}</div>
                    {ref.abstract && <div className="text-sm text-gray-300 mb-1">{ref.abstract}</div>}
                    <div className="text-xs text-gray-400">{[ref.authors, ref.year].filter(Boolean).join(' · ')}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Footer notice: free tier / API key */}
      <div className="fixed inset-x-0 bottom-2 z-50 flex justify-center px-3 mb-safe">
        <div className="text-[11px] md:text-xs text-gray-200 bg-black/50 border border-white/10 rounded-md px-3 py-2 backdrop-blur-sm">
          This beta is limited to 2 questions on low/med resource settings. To enable o3-pro, use your API key to start or contact the creator.
        </div>
      </div>
    </div>
  );
};

export default ResultsPage; 