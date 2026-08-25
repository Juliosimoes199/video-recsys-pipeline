import { useParams } from 'react-router-dom'
import { SignedIn, useAuth } from '@clerk/clerk-react'
import { useChannel, useSubscribe } from '../hooks/useChannel'
import { VideoGrid } from '../components/VideoGrid'

export function Channel() {
  const { channelId } = useParams<{ channelId: string }>()
  const { data: channel, isLoading } = useChannel(channelId)
  const { userId } = useAuth()
  const subscribe = useSubscribe(channelId)

  if (isLoading) return <p className="text-sm text-[var(--text-muted)]">Carregando canal...</p>
  if (!channel) return <p className="text-sm text-[var(--text-muted)]">Canal não encontrado.</p>

  const isOwnChannel = userId === channel.id

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 border-b border-[var(--border)] pb-6">
        {channel.avatarUrl ? (
          <img src={channel.avatarUrl} alt="" className="h-20 w-20 rounded-full" />
        ) : (
          <div className="h-20 w-20 rounded-full bg-[var(--bg-elevated)]" />
        )}
        <div className="flex-1">
          <h1 className="text-xl font-semibold">{channel.displayName}</h1>
          <p className="text-sm text-[var(--text-muted)]">
            {channel.subscriberCount} inscritos · {channel.videos.length} vídeos
          </p>
          {channel.bio && <p className="mt-1 text-sm">{channel.bio}</p>}
        </div>

        {!isOwnChannel && (
          <SignedIn>
            <button
              onClick={() => subscribe.mutate('subscribe')}
              className="rounded-full bg-[var(--text)] px-4 py-2 text-sm font-medium text-black hover:opacity-90"
            >
              Inscrever-se
            </button>
          </SignedIn>
        )}
      </div>

      <div className="mt-6">
        <VideoGrid videos={channel.videos} emptyMessage="Este canal ainda não publicou vídeos." />
      </div>
    </div>
  )
}
