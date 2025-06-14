import pandas as pd
import random

def carregar_filmes(caminho="tmdb_dataset.csv"):
    df = pd.read_csv(caminho)
    df = df.dropna(subset=["title", "overview", "poster_path"])
    df = df.head(300)  # Limita aos 300 primeiros filmes

    df["genero"] = df["genres"].fillna("Desconhecido")
    df["streaming"] = "Netflix"
    df["capa_url"] = "https://image.tmdb.org/t/p/w500" + df["poster_path"]
    df["link"] = df.get("homepage", "")  # link de onde assistir

    return df[["id", "title", "genero", "overview", "streaming", "capa_url", "link"]]

def filme_aleatorio(df, ids_excluidos):
    df_filtrado = df[~df["id"].isin(ids_excluidos)]
    if df_filtrado.empty:
        return None
    return df_filtrado.sample(n=1).iloc[0]
