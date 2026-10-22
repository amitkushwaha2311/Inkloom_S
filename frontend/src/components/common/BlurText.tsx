import React, { useEffect, useRef, useState } from 'react'

interface BlurTextProps {
  text: string
  className?: string
  wordClassName?: string
  onComplete?: () => void
  threshold?: number
}

export const BlurText: React.FC<BlurTextProps> = ({
  text,
  className = '',
  wordClassName = '',
  onComplete,
  threshold = 0.1,
}) => {
  const containerRef = useRef<HTMLHeadingElement | null>(null)
  const [inView, setInView] = useState(false)

  const words = text.split(' ')

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { threshold }
    )

    if (containerRef.current) {
      observer.observe(containerRef.current)
    }

    return () => observer.disconnect()
  }, [threshold])

  useEffect(() => {
    if (inView && onComplete) {
      const totalDelay = (words.length - 1) * 100 + 700
      const timer = setTimeout(onComplete, totalDelay)
      return () => clearTimeout(timer)
    }
  }, [inView, onComplete, words.length])

  return (
    <h1
      ref={containerRef}
      className={`flex flex-wrap items-baseline gap-y-1 ${className}`}
    >
      {words.map((word, i) => {
        const delayMs = i * 100
        return (
          <span
            key={`${word}-${i}`}
            className={`inline-block mr-[0.28em] transition-all duration-700 ease-out will-change-[transform,opacity,filter] ${wordClassName}`}
            style={{
              transitionDelay: `${delayMs}ms`,
              opacity: inView ? 1 : 0,
              filter: inView ? 'blur(0px)' : 'blur(10px)',
              transform: inView ? 'translateY(0)' : 'translateY(50px)',
            }}
          >
            {word}
          </span>
        )
      })}
    </h1>
  )
}
