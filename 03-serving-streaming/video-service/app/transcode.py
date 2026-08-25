"""
Transcodificação com FFmpeg — alternativa ao AWS MediaConvert.

Baixa o vídeo bruto do MinIO, gera HLS adaptativo (3 qualidades + master
playlist) numa passada só de ffmpeg, extrai uma thumbnail, sobe tudo de
volta pro MinIO em hls/{video_id}/.

Usa `asyncio.create_subprocess_exec` (não `subprocess.run`). Isso importa:
o video-service inteiro roda num único processo async (uvicorn). Se você
chamar `subprocess.run` (bloqueante) direto dentro de uma rota async, ele
trava a *event loop inteira* — nenhuma outra requisição (nem `GET /health`)
é atendida enquanto o ffmpeg roda. Com `create_subprocess_exec` o processo
do ffmpeg roda à parte e o `await` só libera o loop pra outras tasks
enquanto espera ele terminar.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile

from . import storage

# name/height/bitrate de cada rendition. Ajustável — mais qualidades =
# melhor adaptação de banda pro espectador, mas mais tempo de CPU por vídeo
# enviado (são N passadas de encoding simultâneas, não sequenciais, mas
# ainda assim N vezes o trabalho de encoding de vídeo).
RENDITIONS = [
    {"name": "480p", "height": 480, "video_bitrate": "1400k", "audio_bitrate": "128k"},
    {"name": "720p", "height": 720, "video_bitrate": "2800k", "audio_bitrate": "128k"},
    {"name": "1080p", "height": 1080, "video_bitrate": "5000k", "audio_bitrate": "192k"},
]


class TranscodeError(RuntimeError):
    pass


async def _run(*args: str) -> None:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise TranscodeError(f"{args[0]} falhou: {stderr.decode(errors='ignore')[-2000:]}")


async def _probe_duration(path: str) -> int:
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    data = json.loads(stdout or b"{}")
    return int(float(data.get("format", {}).get("duration", 0) or 0))


async def _probe_height(path: str) -> int:
    """Altura (em pixels) do primeiro stream de vídeo — usada pra nunca
    gerar uma rendition maior que o vídeo original (isso seria upscale:
    gasta CPU e espaço sem ganhar qualidade nenhuma de verdade)."""
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=height",
        "-of", "json",
        path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    data = json.loads(stdout or b"{}")
    streams = data.get("streams", [])
    return int(streams[0]["height"]) if streams else 0


def _renditions_for(source_height: int) -> list[dict]:
    """Só as renditions que não fazem upscale do vídeo original. Se o
    vídeo original for menor que a menor rendition da tabela (ex.: alguém
    sobe um vídeo em 240p), gera uma única rendition na altura real do
    vídeo em vez de forçar uma das opções fixas."""
    kept = [r for r in RENDITIONS if r["height"] <= source_height]
    if kept:
        return kept

    # Nenhuma rendition da tabela cabe — cria uma sob medida. Altura par
    # (exigência do libx264 com yuv420p) e bitrate escalado a partir do
    # ponto de referência do 480p (1400k a 480px).
    height = source_height - (source_height % 2)
    if height <= 0:
        height = 2
    bitrate_kbps = max(300, round(height * 1400 / 480))
    return [
        {
            "name": f"{height}p",
            "height": height,
            "video_bitrate": f"{bitrate_kbps}k",
            "audio_bitrate": "96k",
        }
    ]


def _content_type_for(filename: str) -> str | None:
    if filename.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    if filename.endswith(".ts"):
        return "video/mp2t"
    if filename.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    return None


async def transcode_video(video_id: str, raw_key: str) -> dict:
    with tempfile.TemporaryDirectory() as workdir:
        input_path = os.path.join(workdir, "input.mp4")
        storage.download_file(raw_key, input_path)

        duration = await _probe_duration(input_path)
        source_height = await _probe_height(input_path)
        renditions = _renditions_for(source_height)

        thumb_path = os.path.join(workdir, "thumbnail.jpg")
        thumb_offset = min(3, max(duration - 1, 0))
        await _run(
            "ffmpeg", "-y",
            "-ss", str(thumb_offset),
            "-i", input_path,
            "-frames:v", "1",
            thumb_path,
        )
        thumb_key = f"{storage.hls_prefix(video_id)}/thumbnail.jpg"
        storage.upload_file(thumb_path, thumb_key, "image/jpeg")

        # ffmpeg não cria diretórios sozinho pro padrão de saída "%v/..." —
        # tem que existir antes de rodar o comando.
        for rendition in renditions:
            os.makedirs(os.path.join(workdir, rendition["name"]), exist_ok=True)

        cmd = ["ffmpeg", "-y", "-i", input_path]

        # Um -map v + -map a por rendition: manda o ffmpeg gerar N saídas
        # de vídeo+áudio a partir da MESMA entrada decodificada uma vez só.
        for _ in renditions:
            cmd += ["-map", "0:v:0", "-map", "0:a:0"]

        var_stream_map = []
        for i, rendition in enumerate(renditions):
            cmd += [
                f"-c:v:{i}", "libx264",
                f"-b:v:{i}", rendition["video_bitrate"],
                f"-filter:v:{i}", f"scale=-2:{rendition['height']}",
                f"-c:a:{i}", "aac",
                f"-b:a:{i}", rendition["audio_bitrate"],
            ]
            var_stream_map.append(f"v:{i},a:{i},name:{rendition['name']}")

        cmd += [
            "-f", "hls",
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-hls_flags", "independent_segments",
            "-master_pl_name", "master.m3u8",
            # "name:" no var_stream_map faz o %v virar o nome da rendition
            # (ex.: "720p") em vez de um índice numérico — só isso já deixa
            # os arquivos de saída legíveis.
            "-var_stream_map", " ".join(var_stream_map),
            os.path.join(workdir, "%v", "stream.m3u8"),
        ]

        await _run(*cmd)

        for root, _dirs, files in os.walk(workdir):
            for filename in files:
                if filename in ("input.mp4", "thumbnail.jpg"):
                    continue
                local_path = os.path.join(root, filename)
                rel_path = os.path.relpath(local_path, workdir)
                key = f"{storage.hls_prefix(video_id)}/{rel_path}"
                storage.upload_file(local_path, key, _content_type_for(filename))

        manifest_key = f"{storage.hls_prefix(video_id)}/master.m3u8"
        return {
            "manifestUrl": storage.public_url(manifest_key),
            "thumbnailUrl": storage.public_url(thumb_key),
            "durationSeconds": duration,
        }
