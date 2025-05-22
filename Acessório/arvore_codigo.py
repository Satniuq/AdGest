import os

# Lista de diretórios (base names) que não serão expandidos
SKIP_EXPAND = {'.git', 'venv', '__pycache__', 'logs', 'migrations', 'migrations_old', 'migrations_old2', 'versions', 'instance'}

def print_tree(path, indent=""):
    """
    Imprime recursivamente a árvore de diretórios a partir do caminho especificado.
    """
    name = os.path.basename(path) if os.path.basename(path) else path

    if os.path.isdir(path):
        print(indent + name + "/")
        # Se o nome do diretório estiver na lista, não expande seu conteúdo
        if name in SKIP_EXPAND:
            return

        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            print(indent + "    [Acesso negado]")
            return

        for entry in entries:
            full_path = os.path.join(path, entry)
            print_tree(full_path, indent + "    ")
    else:
        print(indent + name)

if __name__ == "__main__":
    root_path = r"C:\Python\AdGest - Cópia"
    print_tree(root_path)
