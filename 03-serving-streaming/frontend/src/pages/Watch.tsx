import { useEffect, useRef } from 'react'
import { Link, useParams } from 'react-router-dom'
import { SignedIn } from '@clerk/clerk-react'
import { useVideo } from '../hooks/useVideos'
import { useLikeVideo, useRegisterView } from '../hooks/useVideoActions'
import { VideoPlayer } from '../components/VideoPlayer'
import { CommentSection } from '../components/CommentSection'
import { formatRelativeTime, formatViews } from '../lib/format'

export function Watch() {
  const { videoId } = useParams<{ videoId: string }>()
  const { data: video, isLoading } = useVideo(videoId)
  const registerView = useRegisterView(videoId)
  const likeVideo = useLikeVideo(videoId)
  const viewRegistered = useRef(false)

  useEffect(() => {
    if (video?.status === 'ready' && !viewRegistered.current) {
      viewRegistered.current = true
      registerView.mutate()
    }
  }, [video?.status, registerView])

  if (isLoading) {
    return <p className="text-sm text-[var(--text-muted)]">Carregando vídeo...</p>
  }

  if (!video) {
    return <p className="text-sm text-[var(--text-muted)]">Vídeo não encontrado.</p>
  }

  return (
    <div className="mx-auto max-w-4xl">
      {video.status === 'ready' ? (
        <VideoPlayer video={video} />
      ) : (
        <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-xl bg-[var(--bg-elevated)]">
          <p className="text-sm text-[var(--text-muted)]">
            {video.status === 'failed' ? 'Falha ao processar este vídeo.' : 'Processando vídeo...'}
          </p>
        </div>
      )}

      <div className="mt-4 flex items-center gap-2">
        <h1 className="text-xl font-semibold">{video.title}</h1>
        {video.source === 'youtube' && (
          <span className="shrink-0 rounded-full bg-[var(--bg-elevated)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
            via YouTube
          </span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <Link to={`/channel/${video.channel.id}`} className="flex items-center gap-3">
          {video.channel.avatarUrl ? (
            <img src={video.channel.avatarUrl} alt="" className="h-10 w-10 rounded-full" />
          ) : (
            <div className="h-10 w-10 rounded-full bg-[var(--bg-elevated)]" />
          )}
          <span className="text-sm font-medium">{video.channel.displayName}</span>
        </Link>

        <SignedIn>
          <div className="flex items-center gap-2">
            <button
              onClick={() => likeVideo.mutate('like')}
              className="flex items-center gap-1.5 rounded-full bg-[var(--bg-elevated)] px-4 py-2 text-sm hover:bg-[var(--bg-hover)]"
            >
              👍 {video.likeCount}
            </button>
            <button
              onClick={() => likeVideo.mutate('dislike')}
              className="rounded-full bg-[var(--bg-elevated)] px-4 py-2 text-sm hover:bg-[var(--bg-hover)]"
            >
              👎
            </button>
          </div>
        </SignedIn>
      </div>

      <div className="mt-4 rounded-xl bg-[var(--bg-elevated)] p-3 text-sm">
        <p className="font-medium text-[var(--text-muted)]">
          {formatViews(video.viewCount)} visualizações · {formatRelativeTime(video.createdAt)}
        </p>
        <p className="mt-2 whitespace-pre-wrap">{video.description}</p>
      </div>

      <CommentSection videoId={video.id} />
    </div>
  )
}
