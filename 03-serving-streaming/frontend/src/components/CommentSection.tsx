import { useState, type FormEvent } from 'react'
import { SignedIn, SignedOut } from '@clerk/clerk-react'
import { useAddComment, useComments } from '../hooks/useComments'
import { formatRelativeTime } from '../lib/format'

export function CommentSection({ videoId }: { videoId: string }) {
  const { data, isLoading } = useComments(videoId)
  const addComment = useAddComment(videoId)
  const [text, setText] = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    addComment.mutate(text.trim(), { onSuccess: () => setText('') })
  }

  return (
    <div className="mt-6">
      <h2 className="mb-4 text-sm font-medium">{data?.items.length ?? 0} comentários</h2>

      <SignedIn>
        <form onSubmit={handleSubmit} className="mb-6 flex gap-3">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Adicione um comentário..."
            className="flex-1 border-b border-[var(--border)] bg-transparent pb-1 text-sm outline-none focus:border-[var(--accent)]"
          />
          <button
            type="submit"
            disabled={!text.trim() || addComment.isPending}
            className="rounded-full bg-[var(--accent)] px-4 py-1.5 text-sm font-medium text-black disabled:opacity-40"
          >
            Comentar
          </button>
        </form>
      </SignedIn>
      <SignedOut>
        <p className="mb-6 text-sm text-[var(--text-muted)]">Entre na sua conta para comentar.</p>
      </SignedOut>

      {isLoading && <p className="text-sm text-[var(--text-muted)]">Carregando comentários...</p>}

      <div className="space-y-4">
        {data?.items.map((comment) => (
          <div key={comment.id} className="flex gap-3">
            {comment.authorAvatarUrl ? (
              <img src={comment.authorAvatarUrl} alt="" className="h-8 w-8 shrink-0 rounded-full" />
            ) : (
              <div className="h-8 w-8 shrink-0 rounded-full bg-[var(--bg-elevated)]" />
            )}
            <div>
              <p className="text-xs font-medium">
                {comment.authorName}{' '}
                <span className="ml-1 font-normal text-[var(--text-muted)]">
                  {formatRelativeTime(comment.createdAt)}
                </span>
              </p>
              <p className="mt-0.5 text-sm">{comment.text}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
