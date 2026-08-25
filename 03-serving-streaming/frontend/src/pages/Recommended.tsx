import { useCallback, useEffect, useRef, useState } from 'react'
import { useUser, UserButton } from '@clerk/clerk-react'

interface FeedVideo {
  id: string
  titulo: string
  duracao: number
  url: string
  score: number | null
}

function logEvent(userId: string, videoId: string, eventType: string, watchSeconds?: number) {
  fetch('/api/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId: userId, videoId, eventType, watchSeconds }),
    keepalive: true,
  }).catch(() => {})
}

export function Recommended() {
  const { user } = useUser()
  const userId = user!.id // rota protegida por <ProtectedRoute>, sempre logado aqui

  const [feed, setFeed] = useState<FeedVideo[]>([])
  const [liked, setLiked] = useState<string[]>([])
  const [disliked, setDisliked] = useState<string[]>([])
  const [loadingMore, setLoadingMore] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)

  const stateRef = useRef({ feed, liked, disliked, loadingMore })
  stateRef.current = { feed, liked, disliked, loadingMore }

  // guarda o vídeo/hora de início "ativos" pra fechar o tempo de visualização
  // quando o usuário desliza pro próximo, sem depender de abrir/fechar modal
  const watchingRef = useRef<{ videoId: string | null; startedAt: number }>({
    videoId: null,
    startedAt: 0,
  })

  const carregarMais = useCallback(async () => {
    const { feed, liked, disliked, loadingMore } = stateRef.current
    if (loadingMore) return
    setLoadingMore(true)
    try {
      const resposta = await fetch('/api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          likedIds: liked,
          dislikedIds: disliked,
          excludeIds: feed.map((v) => v.id),
          limit: 8,
        }),
      })
      const dados = await resposta.json()
      setFeed((prev) => [...prev, ...(dados.recomendacoes ?? [])])
    } finally {
      setLoadingMore(false)
    }
  }, [])

  // primeira leva
  useEffect(() => {
    carregarMais()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // pede mais quando o vídeo ativo se aproxima do fim do que já foi carregado
  useEffect(() => {
    if (loadingMore) return
    if (feed.length > 0 && activeIndex >= feed.length - 3) {
      carregarMais()
    }
  }, [activeIndex, feed.length, loadingMore, carregarMais])

  // troca de vídeo ativo (por deslize): fecha o tempo de visualização do
  // anterior e abre o do novo — substitui o antigo par abrir/fechar modal
  useEffect(() => {
    const videoAtual = feed[activeIndex]
    const anterior = watchingRef.current

    if (anterior.videoId) {
      logEvent(userId, anterior.videoId, 'watch', (Date.now() - anterior.startedAt) / 1000)
    }

    if (videoAtual) {
      logEvent(userId, videoAtual.id, 'play')
      watchingRef.current = { videoId: videoAtual.id, startedAt: Date.now() }
    } else {
      watchingRef.current = { videoId: null, startedAt: 0 }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeIndex, feed[activeIndex]?.id])

  // fecha o tempo de visualização do último vídeo ao sair da página
  useEffect(() => {
    function registrarSaida() {
      const atual = watchingRef.current
      if (atual.videoId) {
        logEvent(userId, atual.videoId, 'watch', (Date.now() - atual.startedAt) / 1000)
      }
    }
    window.addEventListener('beforeunload', registrarSaida)
    return () => {
      window.removeEventListener('beforeunload', registrarSaida)
      registrarSaida()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // detecta qual vídeo está visível na tela conforme o usuário desliza
  const observerRef = useRef<IntersectionObserver | null>(null)
  useEffect(() => {
    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && entry.intersectionRatio >= 0.6) {
            setActiveIndex(Number((entry.target as HTMLElement).dataset.index))
          }
        }
      },
      { threshold: [0.6] },
    )
    return () => observerRef.current?.disconnect()
  }, [])

  const registerSlide = useCallback((el: HTMLDivElement | null) => {
    if (el && observerRef.current) observerRef.current.observe(el)
  }, [])

  function toggleLike(id: string) {
    const jaCurtido = liked.includes(id)
    setLiked((prev) => (jaCurtido ? prev.filter((v) => v !== id) : [...prev, id]))
    logEvent(userId, id, jaCurtido ? 'unlike' : 'like')
    if (!jaCurtido && disliked.includes(id)) {
      setDisliked((prev) => prev.filter((v) => v !== id))
      logEvent(userId, id, 'undislike')
    }
  }

  function toggleDislike(id: string) {
    const jaDescurtido = disliked.includes(id)
    setDisliked((prev) => (jaDescurtido ? prev.filter((v) => v !== id) : [...prev, id]))
    logEvent(userId, id, jaDescurtido ? 'undislike' : 'dislike')
    if (!jaDescurtido && liked.includes(id)) {
      setLiked((prev) => prev.filter((v) => v !== id))
      logEvent(userId, id, 'unlike')
    }
  }

  return (
    <div className="fixed inset-0 bg-black">
      <div className="absolute right-3 top-3 z-20">
        <UserButton afterSignOutUrl="/" />
      </div>

      <div className="reels-scroll h-dvh w-full snap-y snap-mandatory overflow-y-scroll">
        {feed.map((video, index) => (
          <div
            key={video.id}
            ref={registerSlide}
            data-index={index}
            className="relative flex h-dvh w-full snap-start items-center justify-center bg-black"
            style={{ scrollSnapStop: 'always' }}
          >
            {index === activeIndex ? (
              <iframe
                className="h-full w-full"
                src={`https://www.youtube.com/embed/${video.id}?autoplay=1&mute=1&loop=1&playlist=${video.id}&playsinline=1`}
                title={video.titulo}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            ) : (
              <img
                src={`https://img.youtube.com/vi/${video.id}/hqdefault.jpg`}
                alt=""
                className="h-full w-full object-cover opacity-70"
                loading="lazy"
              />
            )}

            <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-4 pb-8">
              <p className="line-clamp-2 max-w-[75%] text-sm font-medium text-white">{video.titulo}</p>
            </div>

            <div className="absolute bottom-24 right-3 flex flex-col items-center gap-6">
              <button
                onClick={() => toggleLike(video.id)}
                aria-label={liked.includes(video.id) ? 'Descurtir' : 'Curtir'}
                className="flex flex-col items-center"
              >
                <span
                  className="text-3xl drop-shadow-lg"
                  style={{ color: liked.includes(video.id) ? 'var(--accent)' : '#ffffff' }}
                >
                  {liked.includes(video.id) ? '♥' : '♡'}
                </span>
              </button>
              <button
                onClick={() => toggleDislike(video.id)}
                aria-label={disliked.includes(video.id) ? 'Remover não gostei' : 'Não gostei'}
                className="flex flex-col items-center"
              >
                <span
                  className="text-2xl drop-shadow-lg"
                  style={{ color: disliked.includes(video.id) ? '#ef4444' : '#ffffff' }}
                >
                  👎
                </span>
              </button>
            </div>
          </div>
        ))}
      </div>

      <style>{`
        .reels-scroll::-webkit-scrollbar { display: none; }
        .reels-scroll { scrollbar-width: none; }
      `}</style>
    </div>
  )
}
