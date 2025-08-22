import React, { useRef, useEffect, useState } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';

const AnimatedExamples = ({ examples, isVisible = true }) => {
  const containerRef = useRef(null);
  const textRef = useRef(null);
  const cursorRef = useRef(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [displayText, setDisplayText] = useState('');

  // Timing controls for rotation speed and readability on mobile/iOS
  const typingSecondsPerCharacter = 0.07; // slower type speed
  const deleteSecondsPerCharacter = 0.03; // slower delete speed
  const cursorBlinkDurationSeconds = 0.6; // blink cadence
  const cursorBlinkRepeats = 6; // increased pause via more blinks
  const additionalReadPauseSeconds = 1.2; // extra hold after typing

  useGSAP(() => {
    if (!isVisible || !textRef.current || !cursorRef.current) return;

    const tl = gsap.timeline({ repeat: -1 });
    // Randomize the order each time the timeline is built
    const sequence = gsap.utils.shuffle(examples.slice());

    sequence.forEach((example, index) => {
      // Type out the text character by character
      tl.call(() => {
        setCurrentIndex(index);
        setDisplayText('');
      })
      .to({}, {
        duration: example.length * typingSecondsPerCharacter, // Typing speed
        ease: "none",
        onUpdate: function() {
          const progress = this.progress();
          const charIndex = Math.floor(progress * example.length);
          setDisplayText(example.substring(0, charIndex));
        }
      })
      // Cursor blink during pause
      .to(cursorRef.current, {
        opacity: 0,
        duration: cursorBlinkDurationSeconds,
        repeat: cursorBlinkRepeats,
        yoyo: true,
        ease: "power2.inOut"
      })
      // Extra hold to slow rotation
      .to({}, { duration: additionalReadPauseSeconds })
      // Delete text with faster speed
      .to({}, {
        duration: example.length * deleteSecondsPerCharacter,
        ease: "power2.in",
        onUpdate: function() {
          const progress = 1 - this.progress();
          const charIndex = Math.floor(progress * example.length);
          setDisplayText(example.substring(0, charIndex));
        }
      })
      .set(cursorRef.current, { opacity: 1 });
    });

    return () => tl.kill();
  }, [examples, isVisible]);

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

  if (!isVisible) return null;

  return (
    <div ref={containerRef} className="mb-3 text-center">
      <div className="inline-flex items-center">
        <span 
          ref={textRef}
          className="text-base md:text-lg text-gray-200/90 font-mono"
        >
          "{displayText}"
        </span>
        <span 
          ref={cursorRef}
          className="text-base md:text-lg text-cyan-400 font-mono ml-1"
        >
          |
        </span>
      </div>
    </div>
  );
};

export default AnimatedExamples;
