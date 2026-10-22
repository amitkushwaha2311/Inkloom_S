import React, { useEffect, useRef, useState } from 'react'

interface FadingVideoProps extends React.VideoHTMLAttributes<HTMLVideoElement> {
  src: string
  poster?: string
  className?: string
  fallbackBg?: string
}

const FADE_MS = 500
const FADE_OUT_LEAD = 0.55 // seconds before end to start fading out

export const FadingVideo: React.FC<FadingVideoProps> = ({
  src,
  poster,
  className = '',
  fallbackBg = 'bg-charcoal',
  ...restProps
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const animFrameRef = useRef<number | null>(null)
  const isFadingOutRef = useRef<boolean>(false)
  const [hasError, setHasError] = useState<boolean>(false)

  // Smoothly fade video opacity using requestAnimationFrame
  const fadeTo = (targetOpacity: number, durationMs: number = FADE_MS, onComplete?: () => void) => {
    const video = videoRef.current
    if (!video) return

    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }

    const startOpacity = parseFloat(video.style.opacity || '0')
    if (Math.abs(startOpacity - targetOpacity) < 0.01) {
      video.style.opacity = targetOpacity.toString()
      onComplete?.()
      return
    }

    const startTime = performance.now()

    const step = (currentTime: number) => {
      const elapsed = currentTime - startTime
      const progress = Math.min(1, elapsed / durationMs)
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = startOpacity + (targetOpacity - startOpacity) * eased

      if (video) {
        video.style.opacity = current.toString()
      }

      if (progress < 1) {
        animFrameRef.current = requestAnimationFrame(step)
      } else {
        if (video) video.style.opacity = targetOpacity.toString()
        animFrameRef.current = null
        onComplete?.()
      }
    }

    animFrameRef.current = requestAnimationFrame(step)
  }

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    video.style.opacity = '0'
    isFadingOutRef.current = false

    const handleLoadedData = () => {
      video.style.opacity = '0'
      const playPromise = video.play()
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            fadeTo(1, FADE_MS)
          })
          .catch(() => {
            // Autoplay might be restricted
            setHasError(true)
          })
      }
    }

    const handleTimeUpdate = () => {
      if (!video.duration || isFadingOutRef.current) return
      const remaining = video.duration - video.currentTime
      if (remaining <= FADE_OUT_LEAD && remaining > 0) {
        isFadingOutRef.current = true
        fadeTo(0, FADE_MS)
      }
    }

    const handleEnded = () => {
      video.style.opacity = '0'
      setTimeout(() => {
        if (!video) return
        video.currentTime = 0
        const playPromise = video.play()
        if (playPromise !== undefined) {
          playPromise
            .then(() => {
              isFadingOutRef.current = false
              fadeTo(1, FADE_MS)
            })
            .catch(() => {
              isFadingOutRef.current = false
            })
        }
      }, 100)
    }

    const handleError = () => {
      setHasError(true)
    }

    video.addEventListener('loadeddata', handleLoadedData)
    video.addEventListener('timeupdate', handleTimeUpdate)
    video.addEventListener('ended', handleEnded)
    video.addEventListener('error', handleError)

    // Check if video is already ready
    if (video.readyState >= 2) {
      handleLoadedData()
    }

    return () => {
      if (animFrameRef.current !== null) {
        cancelAnimationFrame(animFrameRef.current)
      }
      video.removeEventListener('loadeddata', handleLoadedData)
      video.removeEventListener('timeupdate', handleTimeUpdate)
      video.removeEventListener('ended', handleEnded)
      video.removeEventListener('error', handleError)
    }
  }, [src])

  if (hasError) {
    return (
      <div
        className={`w-full h-full ${fallbackBg} flex items-center justify-center ${className}`}
        style={{ backgroundImage: poster ? `url(${poster})` : undefined, backgroundSize: 'cover', backgroundPosition: 'center' }}
      />
    )
  }

  return (
    <video
      ref={videoRef}
      src={src}
      poster={poster}
      muted
      playsInline
      preload="auto"
      className={`transition-none pointer-events-none select-none ${className}`}
      {...restProps}
    />
  )
}
