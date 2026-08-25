import sys
import csv
import sqlite3

DB_PATH = "videos.db"


def listar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    linhas = conn.execute("SELECT * FROM videos ORDER BY salvo_em DESC").fetchall()
    conn.close()

    for linha in linhas:
        print(f"[{linha['id']}] {linha['titulo']} ({linha['duracao']}s) — busca: '{linha['termo_busca']}'")
    print(f"\nTotal: {len(linhas)} vídeos")


def exportar_csv(caminho_csv="videos.csv"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT * FROM videos ORDER BY salvo_em DESC")
    colunas = [descricao[0] for descricao in cursor.description]

    with open(caminho_csv, "w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(colunas)
        escritor.writerows(cursor)

    conn.close()
    print(f"Exportado para {caminho_csv}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "csv":
        caminho = sys.argv[2] if len(sys.argv) > 2 else "videos.csv"
        exportar_csv(caminho)
    else:
        listar()
