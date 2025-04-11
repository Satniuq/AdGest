import os
import unicodedata

def get_files_from_directory(directory, valid_exts=None, recursive=True, exclude_dirs=None):
    """
    Retorna uma lista de ficheiros contidos em 'directory'.
    
    Parâmetros:
      - directory: caminho da pasta a processar.
      - valid_exts: lista de extensões válidas (ex.: ['.py']). Se None, retorna todos os ficheiros.
      - recursive: se True, percorre todas as subpastas; se False, apenas a pasta indicada.
      - exclude_dirs: lista de nomes de diretórios a serem excluídos (case-insensitive).
    """
    file_list = []
    exclude_dirs = exclude_dirs or []
    if recursive:
        for root, dirs, files in os.walk(directory):
            # Excluir diretórios que estão na lista de exclusão
            dirs[:] = [d for d in dirs if d.lower() not in [x.lower() for x in exclude_dirs]]
            for file in files:
                if valid_exts:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in valid_exts:
                        file_list.append(os.path.join(root, file))
                else:
                    file_list.append(os.path.join(root, file))
    else:
        for file in os.listdir(directory):
            path = os.path.join(directory, file)
            if os.path.isfile(path):
                if valid_exts:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in valid_exts:
                        file_list.append(path)
                else:
                    file_list.append(path)
    return file_list

def write_group_file(output_file, directories, valid_exts=None, recursive=True, exclude_dirs=None, extra_files=None):
    """
    Escreve num arquivo de saída o conteúdo de todos os ficheiros encontrados nas pastas indicadas.
    
    Parâmetros:
      - output_file: caminho do arquivo de saída.
      - directories: lista de pastas (ou ficheiros) a serem processados.
      - valid_exts: lista de extensões a filtrar (ex.: ['.html']).
      - recursive: se True, percorre recursivamente os diretórios.
      - exclude_dirs: lista de diretórios a serem excluídos.
      - extra_files: lista de arquivos individuais a serem adicionados.
    """
    with open(output_file, 'w', encoding='utf-8') as out:
        for path in directories:
            if os.path.isdir(path):
                files = get_files_from_directory(path, valid_exts, recursive, exclude_dirs)
                for file in files:
                    out.write(f'-- Conteúdo do ficheiro: {file} --\n')
                    try:
                        with open(file, 'r', encoding='utf-8') as f:
                            out.write(f.read())
                    except Exception as e:
                        out.write(f'Erro ao ler o ficheiro: {e}\n')
                    out.write('\n' + '-' * 80 + '\n')
            elif os.path.isfile(path):
                out.write(f'-- Conteúdo do ficheiro: {path} --\n')
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        out.write(f.read())
                except Exception as e:
                    out.write(f'Erro ao ler o ficheiro: {e}\n')
                out.write('\n' + '-' * 80 + '\n')

        if extra_files:
            for file in extra_files:
                if os.path.isfile(file):
                    out.write(f'-- Conteúdo do ficheiro: {file} --\n')
                    try:
                        with open(file, 'r', encoding='utf-8') as f:
                            out.write(f.read())
                    except Exception as e:
                        out.write(f'Erro ao ler o ficheiro: {e}\n')
                    out.write('\n' + '-' * 80 + '\n')

def main():
    # Diretórios base
    base_dir = r"C:\Python\AdGest\app"
    templates_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")
    accounting_dir = os.path.join(base_dir, "accounting")
    templates_accounting_dir = os.path.join(templates_dir, "accounting")

    # Bloco A: Pasta accounting + templates/accounting
    output_group_A = os.path.join(base_dir, "codigo_accounting.txt")
    write_group_file(output_group_A, [accounting_dir, templates_accounting_dir],
                     valid_exts=None, recursive=True)
    print(f'Grupo A (accounting + templates/accounting) salvo em: {output_group_A}')

    # Bloco B: Código e templates gerais (exceto accounting)
    output_group_B = os.path.join(base_dir, "codigo_app_geral.txt")
    # Processa todos os .py dentro da pasta base "app", excluindo a subpasta "accounting"
    write_group_file(output_group_B, [base_dir], valid_exts=['.py'], recursive=True, exclude_dirs=["accounting"])
    # Processa os templates HTML fora da subpasta "accounting"
    write_group_file(output_group_B, [templates_dir], valid_exts=['.html'], recursive=True, exclude_dirs=["accounting"])
    print(f'Grupo B (código e templates gerais, exceto accounting) salvo em: {output_group_B}')

    # Bloco C: Assets – static e similares
    output_group_C = os.path.join(base_dir, "codigo_static.txt")
    write_group_file(output_group_C, [static_dir], valid_exts=None, recursive=True)
    print(f'Grupo C (assets da pasta static) salvo em: {output_group_C}')

if __name__ == '__main__':
    main()
