import os

# Pastas cujos conteúdos não serão listados
SKIP_EXPAND = {"venv", "__pycache__", "logs", "migrations", "migrations_old", "versions"}

def print_tree(path, indent=""):
    # Caso o path esteja vazio, usa o próprio path (útil para a raiz)
    nome = os.path.basename(path) if os.path.basename(path) else path

    # Se for diretório, imprime com barra no final
    if os.path.isdir(path):
        print(indent + nome + "/")
        # Se o nome do diretório estiver na lista de exclusão, não expande seu conteúdo
        if nome in SKIP_EXPAND:
            return
        novo_indent = indent + "    "
        try:
            itens = sorted(os.listdir(path))
        except PermissionError:
            return
        for item in itens:
            print_tree(os.path.join(path, item), novo_indent)
    else:
        print(indent + nome)

if __name__ == "__main__":
    # Substitua pelo caminho da sua pasta de projeto, ex.: "C:\Python\AdGest"
    raiz = r"C:\Python\AdGest"
    print_tree(raiz)
