import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import webbrowser
import threading
from queue import Queue, Empty
from deep_translator import GoogleTranslator
from processador_dataset import carregar_filmes, filme_aleatorio


def traduzir(texto, to_lang="pt"):
    try:
        return GoogleTranslator(source='auto', target=to_lang).translate(texto)
    except Exception:
        return texto


class CineMatchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CineMatch 🎬")
        self.root.geometry("800x600")
        self.root.configure(bg="#121212")
        self.root.minsize(600, 400)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#121212", foreground="white", font=("Helvetica", 14))
        style.configure("Title.TLabel", font=("Helvetica", 20, "bold"))
        style.configure("TButton", font=("Helvetica", 12, "bold"), padding=10)
        style.map("Like.TButton",
                  foreground=[('active', 'white')],
                  background=[('active', '#4caf50'), ('!active', '#388e3c')])
        style.map("Dislike.TButton",
                  foreground=[('active', 'white')],
                  background=[('active', '#e53935'), ('!active', '#b71c1c')])

        self.df = carregar_filmes()
        self.ids_votados = set()
        self.curtidos = []

        self.container = ttk.Frame(root, padding=20)
        self.container.place(relx=0.5, rely=0.5, anchor="center")

        self.frame_filme = ttk.Frame(self.container)
        self.frame_filme.pack()

        self.content_frame = ttk.Frame(self.frame_filme)
        self.content_frame.pack()

        self.capa_label = ttk.Label(self.content_frame)
        self.capa_label.grid(row=0, column=0, padx=(0, 20), sticky="n")

        self.info_label = ttk.Label(self.content_frame, wraplength=450, justify="left", style="TLabel")
        self.info_label.grid(row=0, column=1, sticky="nw")

        self.btn_frame = ttk.Frame(self.container)
        self.btn_frame.pack(pady=15)

        self.btn_like = ttk.Button(self.btn_frame, text="Gostei 👍", style="Like.TButton", command=self.gostei)
        self.btn_like.grid(row=0, column=0, padx=15)

        self.btn_dislike = ttk.Button(self.btn_frame, text="Não Gostei 👎", style="Dislike.TButton", command=self.nao_gostei)
        self.btn_dislike.grid(row=0, column=1, padx=15)

        self.btn_info = ttk.Button(self.container, text="Mais informações 🌐", command=self.abrir_link)
        self.btn_info.pack(pady=(10, 0))
        self.btn_info.pack_forget()

        self.btn_restart = ttk.Button(self.container, text="Reiniciar 🔄", command=self.reiniciar)
        self.btn_restart.pack(pady=(10, 0))
        self.btn_restart.pack_forget()

        # Cache de traduções {id: texto_traduzido}
        self.cache_traducao = {}
        # Fila para pré-tradução
        self.traducao_queue = Queue()
        # Controle de ids votados para pré-traduzir só não votados
        self.ids_votados = set()

        # Start da thread worker para pré-tradução
        threading.Thread(target=self.worker_pretraducao, daemon=True).start()

        self.filme_atual = None
        self.recomendacao_final = None

        self.exibir_filme_aleatorio()
        self.root.bind("<Configure>", self.centralizar_container)

    def centralizar_container(self, event=None):
        self.container.place(relx=0.5, rely=0.5, anchor="center")

    def worker_pretraducao(self):
        while True:
            try:
                filme = self.traducao_queue.get(timeout=5)
            except Empty:
                continue

            if filme["id"] in self.cache_traducao or filme["id"] in self.ids_votados:
                self.traducao_queue.task_done()
                continue

            try:
                title_pt = traduzir(filme["title"])
                genero_pt = traduzir(filme.get("genero", "Desconhecido"))
                overview_pt = traduzir(filme["overview"][:400])
                texto_traduzido = f"{title_pt} ({genero_pt})\n\n{overview_pt}..."
                self.cache_traducao[filme["id"]] = texto_traduzido
            except Exception:
                # Salva original se falhar
                texto_traduzido = f"{filme['title']} ({filme.get('genero', 'Desconhecido')})\n\n{filme['overview'][:400]}..."
                self.cache_traducao[filme["id"]] = texto_traduzido
            finally:
                self.traducao_queue.task_done()

    def exibir_filme_aleatorio(self):
        filme = filme_aleatorio(self.df, self.ids_votados)
        if filme is None:
            self.mostrar_recomendacao()
            return

        self.filme_atual = filme
        self.recomendacao_final = None
        self.btn_info.pack_forget()
        self.btn_restart.pack_forget()

        # Enfileira próximos filmes para pré-traduzir
        self.pretraduzir_filmes_proximos()

        def carregar_dados():
            try:
                response = requests.get(filme["capa_url"], timeout=5)
                response.raise_for_status()
                img_data = Image.open(BytesIO(response.content))

                max_width, max_height = 180, 270
                img_ratio = img_data.width / img_data.height
                target_ratio = max_width / max_height

                if img_ratio > target_ratio:
                    new_width = max_width
                    new_height = int(max_width / img_ratio)
                else:
                    new_height = max_height
                    new_width = int(max_height * img_ratio)

                img_resized = img_data.resize((new_width, new_height), Image.LANCZOS)
                self.img = ImageTk.PhotoImage(img_resized)
                self.capa_label.config(image=self.img)
            except Exception:
                self.capa_label.config(image="")

            # Exibe texto da tradução se disponível, senão traduz na hora
            if filme["id"] in self.cache_traducao:
                texto = self.cache_traducao[filme["id"]]
                self.info_label.config(text=texto)
            else:
                titulo = traduzir(filme['title'])
                overview = traduzir(filme['overview'][:400])
                genero = traduzir(filme.get('genero', 'Desconhecido'))
                texto = f"{titulo} ({genero})\n\n{overview}..."
                self.info_label.config(text=texto)

            self.btn_like.config(state="normal")
            self.btn_dislike.config(state="normal")

        threading.Thread(target=carregar_dados, daemon=True).start()

    def pretraduzir_filmes_proximos(self):
        # Pega próximos 5 filmes não votados e não traduzidos para enfileirar tradução
        filmes_para_pretraduzir = self.df[~self.df['id'].isin(self.ids_votados)].head(5)
        for _, filme in filmes_para_pretraduzir.iterrows():
            if filme["id"] not in self.cache_traducao:
                self.traducao_queue.put(filme)

    def gostei(self):
        self.curtidos.append(self.filme_atual)
        self.ids_votados.add(self.filme_atual["id"])
        if len(self.ids_votados) >= 6:
            self.mostrar_recomendacao()
        else:
            self.exibir_filme_aleatorio()

    def nao_gostei(self):
        self.ids_votados.add(self.filme_atual["id"])
        if len(self.ids_votados) >= 6:
            self.mostrar_recomendacao()
        else:
            self.exibir_filme_aleatorio()

    def mostrar_recomendacao(self):
        self.btn_frame.pack_forget()

        if not self.curtidos:
            texto = "Você não gostou de nenhum filme. Tente novamente!"
            self.capa_label.config(image="")
            self.info_label.config(text=texto)
            self.btn_info.pack_forget()
            self.btn_restart.pack()
            return

        generos = [filme.get('genero', 'Desconhecido') for filme in self.curtidos]
        genero_recomendado = max(set(generos), key=generos.count)

        df_filmes_recomendados = self.df[
            (self.df['genero'] == genero_recomendado) & (~self.df['id'].isin(self.ids_votados))
        ]

        if df_filmes_recomendados.empty:
            filme_recomendado = self.curtidos[0]
        else:
            filme_recomendado = df_filmes_recomendados.sample(n=1).iloc[0]

        self.recomendacao_final = filme_recomendado

        def carregar_recomendacao():
            try:
                response = requests.get(filme_recomendado["capa_url"], timeout=5)
                response.raise_for_status()
                img_data = Image.open(BytesIO(response.content))

                max_width, max_height = 180, 270
                img_ratio = img_data.width / img_data.height
                target_ratio = max_width / max_height

                if img_ratio > target_ratio:
                    new_width = max_width
                    new_height = int(max_width / img_ratio)
                else:
                    new_height = max_height
                    new_width = int(max_height * img_ratio)

                img_resized = img_data.resize((new_width, new_height), Image.LANCZOS)
                self.img = ImageTk.PhotoImage(img_resized)
                self.capa_label.config(image=self.img)
            except Exception:
                self.capa_label.config(image="")

            # Usa cache se disponível
            if filme_recomendado["id"] in self.cache_traducao:
                texto = self.cache_traducao[filme_recomendado["id"]]
                self.info_label.config(text=texto)
            else:
                titulo = traduzir(filme_recomendado['title'])
                overview = traduzir(filme_recomendado['overview'][:400])
                genero = traduzir(filme_recomendado.get('genero', 'Desconhecido'))
                texto = (f"🎉 Recomendação para você: \n\n"
                         f"{titulo} ({genero})\n\n"
                         f"{overview}...")
                self.info_label.config(text=texto)

            self.btn_info.pack()
            self.btn_restart.pack()

        threading.Thread(target=carregar_recomendacao, daemon=True).start()

    def reiniciar(self):
        self.ids_votados.clear()
        self.curtidos.clear()
        self.cache_traducao.clear()
        self.recomendacao_final = None
        self.btn_info.pack_forget()
        self.btn_restart.pack_forget()
        self.btn_frame.pack()
        self.exibir_filme_aleatorio()

    def abrir_link(self):
        if self.recomendacao_final is not None:
            link = self.recomendacao_final.get("link", "")
            if link and isinstance(link, str):
                webbrowser.open(link)


if __name__ == "__main__":
    root = tk.Tk()
    app = CineMatchApp(root)
    root.mainloop()
