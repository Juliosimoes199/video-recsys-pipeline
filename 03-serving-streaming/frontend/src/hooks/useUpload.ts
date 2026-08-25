import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@clerk/clerk-react'
import { useApiClient } from '../lib/api'
import type { PresignResponse, Video, Visibility } from '../types'

interface UploadInput {
  file: File
  title: string
  description: string
  visibility: Visibility
  onProgress?: (percent: number) => void
}

const MAX_CONCURRENT_PARTS = 4

function uploadPart(url: string, blob: Blob, onBytes: (loaded: number) => void): Promise<string> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', url)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onBytes(event.loaded)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const etag = xhr.getResponseHeader('ETag')
        if (!etag) {
          reject(
            new Error(
              'O MinIO não devolveu o header ETag — confira o CORS (ExposeHeaders precisa ter "ETag").',
            ),
          )
          return
        }
        resolve(etag)
      } else {
        reject(new Error(`Falha ao enviar parte do vídeo (status ${xhr.status})`))
      }
    }
    xhr.onerror = () => reject(new Error('Falha de rede ao enviar parte do vídeo'))
    xhr.send(blob)
  })
}

async function uploadPartsWithConcurrency(
  file: File,
  parts: PresignResponse['parts'],
  partSize: number,
  onProgress?: (percent: number) => void,
): Promise<{ partNumber: number; etag: string }[]> {
  const loadedByPart = new Array(parts.length).fill(0)
  const results: { partNumber: number; etag: string }[] = new Array(parts.length)

  function reportProgress() {
    if (!onProgress) return
    const loaded = loadedByPart.reduce((a, b) => a + b, 0)
    onProgress(Math.min(100, Math.round((loaded / file.size) * 100)))
  }

  let nextIndex = 0
  async function worker() {
    while (nextIndex < parts.length) {
      const index = nextIndex++
      const part = parts[index]
      const start = (part.partNumber - 1) * partSize
      const end = Math.min(start + partSize, file.size)
      const blob = file.slice(start, end)

      const etag = await uploadPart(part.url, blob, (loaded) => {
        loadedByPart[index] = loaded
        reportProgress()
      })

      loadedByPart[index] = blob.size
      results[index] = { partNumber: part.partNumber, etag }
      reportProgress()
    }
  }

  const workerCount = Math.min(MAX_CONCURRENT_PARTS, parts.length)
  await Promise.all(Array.from({ length: workerCount }, worker))
  return results
}

export function useUploadVideo() {
  const api = useApiClient()
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ file, title, description, visibility, onProgress }: UploadInput) => {
      if (!(await getToken())) {
        throw new Error('É preciso estar logado para enviar um vídeo.')
      }

      const { data: presign } = await api.post<PresignResponse>('/videos/upload/presign', {
        filename: file.name,
        contentType: file.type || 'application/octet-stream',
        sizeBytes: file.size,
      })

      const uploadedParts = await uploadPartsWithConcurrency(
        file,
        presign.parts,
        presign.partSize,
        onProgress,
      )

      const { data: video } = await api.post<Video>(`/videos/${presign.videoId}/complete`, {
        title,
        description,
        visibility,
        parts: uploadedParts,
      })

      return video
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['videos'] })
      queryClient.invalidateQueries({ queryKey: ['my-videos'] })
    },
  })
}
