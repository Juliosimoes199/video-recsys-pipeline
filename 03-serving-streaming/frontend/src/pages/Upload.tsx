import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUploadVideo } from '../hooks/useUpload'
import type { Visibility } from '../types'

export function Upload() {
  const navigate = useNavigate()
  const uploadVideo = useUploadVideo()

  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [visibility, setVisibility] = useState<Visibility>('public')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (!file) {
      setError('Selecione um arquivo de vídeo.')
      return
    }

    try {
      const video = await uploadVideo.mutateAsync({
        file,
        title: title || file.name,
        description,
        visibility,
        onProgress: setProgress,
      })
      navigate(`/watch/${video.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro inesperado ao enviar o vídeo.')
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-xl font-semibold">Enviar vídeo</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="mb-2 block text-sm font-medium text-[var(--text-muted)]">Arquivo de vídeo</label>
          <input
            type="file"
            accept="video/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full cursor-pointer rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-4 text-sm file:mr-4 file:cursor-pointer file:rounded-md file:border-0 file:bg-[var(--accent)] file:px-4 file:py-2 file:font-medium file:text-black"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--text-muted)]">Título</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Dê um título para o seu vídeo"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--text-muted)]">Descrição</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            placeholder="Conte um pouco sobre o vídeo"
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-[var(--text-muted)]">Visibilidade</label>
          <select
            value={visibility}
            onChange={(e) => setVisibility(e.target.value as Visibility)}
            className="w-full rounded-md border border-[var(--border)] bg-transparent px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
          >
            <option value="public">Público</option>
            <option value="unlisted">Não listado</option>
            <option value="private">Privado</option>
          </select>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        {uploadVideo.isPending ? (
          <div className="space-y-2 rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] p-4">
            <div className="flex items-center justify-between text-sm">
              <span>Enviando...</span>
              <span className="tabular-nums text-[var(--text-muted)]">{progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
              <div
                className="h-full rounded-full bg-[var(--accent)] transition-[width] duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        ) : (
          <button
            type="submit"
            className="w-full rounded-md bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-black hover:opacity-90"
          >
            Publicar
          </button>
        )}
      </form>
    </div>
  )
}
