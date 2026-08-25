import { useEffect, useRef } from 'react'
import Hls from 'hls.js'
import type { Video } from '../types'

interface VideoPlayerProps {
  video: Video
}

export function VideoPlayer({ video }: VideoPlayerProps) {
  if (video.source === 'youtube' && video.externalId) {
    return <YouTubeEmbed videoId={video.externalId} title={video.title} />
  }

  if (video.manifestUrl) {
    return <HlsPlayer manifestUrl={video.manifestUrl} poster={video.thumbnailUrl} />
  }

  return null
}

/**
 * Vídeo importado da API do YouTube (ver video-service/scripts/seed_youtube.py):
 * tocamos pelo player oficial embutido deles, não temos (nem podemos ter,
 * pelos Termos de Serviço da API) uma cópia do vídeo nos nossos servidores.
 */
function YouTubeEmbed({ videoId, title }: { videoId: string; title: string }) {
  return (
    <iframe
      className="aspect-video w-full rounded-xl bg-black"
      src={`https://www.youtube.com/embed/${videoId}`}
      title={title}
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      allowFullScreen
    />
  )
}

function HlsPlayer({ manifestUrl, poster }: { manifestUrl: string; poster?: string | null }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = manifestUrl
      return
    }

    if (Hls.isSupported()) {
      const hls = new Hls()
      hls.loadSource(manifestUrl)
      hls.attachMedia(video)
      return () => hls.destroy()
    }

    video.src = manifestUrl
  }, [manifestUrl])

  return (
    <video
      ref={videoRef}
      controls
      autoPlay
      poster={poster ?? undefined}
      className="w-full aspect-video rounded-xl bg-black"
    />
  )
}
