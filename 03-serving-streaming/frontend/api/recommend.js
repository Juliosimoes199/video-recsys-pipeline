import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import path from 'path'

const dataDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '_data')
const catalog = JSON.parse(readFileSync(path.join(dataDir, 'catalog.json'), 'utf-8'))
const embeddings = JSON.parse(readFileSync(path.join(dataDir, 'embeddings.json'), 'utf-8'))

function cosseno(a, b) {
  let dot = 0
  let na = 0
  let nb = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    na += a[i] * a[i]
    nb += b[i] * b[i]
  }
  return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-8)
}

function mediaEmbeddings(indices) {
  const dim = embeddings[0].length
  const media = new Array(dim).fill(0)
  for (const i of indices) {
    for (let d = 0; d < dim; d++) media[d] += embeddings[i][d] / indices.length
  }
  return media
}

export default function handler(req, res) {
  const body = req.method === 'POST' ? (req.body ?? {}) : {}
  const likedIds = Array.isArray(body.likedIds) ? body.likedIds : []
  const dislikedIds = Array.isArray(body.dislikedIds) ? body.dislikedIds : []
  const excludeIds = new Set(Array.isArray(body.excludeIds) ? body.excludeIds : [])
  const limit = Number.isInteger(body.limit) ? body.limit : 12

  const disponiveis = catalog
    .map((video, i) => ({ video, i }))
    .filter(({ video }) => !excludeIds.has(video.id))

  const idxCurtidos = likedIds
    .map((id) => catalog.findIndex((v) => v.id === id))
    .filter((i) => i !== -1)

  // sem sinal ainda (feed "descubra"): ordem do catálogo, só pulando o que já apareceu
  if (idxCurtidos.length === 0) {
    const pagina = disponiveis.slice(0, limit).map(({ video }) => ({ ...video, score: null }))
    res.status(200).json({ recomendacoes: pagina })
    return
  }

  const idxDescurtidos = dislikedIds
    .map((id) => catalog.findIndex((v) => v.id === id))
    .filter((i) => i !== -1)

  const vetorGostei = mediaEmbeddings(idxCurtidos)
  const vetorNaoGostei = idxDescurtidos.length > 0 ? mediaEmbeddings(idxDescurtidos) : null

  const ranking = disponiveis
    .map(({ video, i }) => {
      let score = cosseno(vetorGostei, embeddings[i])
      if (vetorNaoGostei) {
        score -= 0.5 * cosseno(vetorNaoGostei, embeddings[i])
      }
      return { video, score }
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(({ video, score }) => ({ ...video, score }))

  res.status(200).json({ recomendacoes: ranking })
}
