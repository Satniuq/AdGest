#FAZER CORRER O CÓDIGO: 
# python extract_routes.py --routes app/routes.py --templates app/templates --models app/models.py --forms app/forms.py --exts .py .html

import os
import re
import argparse
import string

# Arquivos com nomes genéricos – usaremos extração por blocos nesses casos
GENERIC_FILES = {"models.py", "forms.py"}

# Atualize este dicionário conforme as marcações que você usa nos seus arquivos.
# Acrescentei palavras-chave para identificar blocos como "MODEL USER", "FORM REGISTAR", "FORM LOGIN", etc.
GROUP_MAPPING = {
    "auth": ["login", "profile", "register", "autenticação", "user", "form registar", "form login", "form register"],
    "billing": ["billing", "nota", "honorario"],
    "clientes": ["client", "cliente", "clientes", "partilhar_client"],
    "contabilidade": ["contabil", "accounting", "invoice", "documento", "invoices"],
    "assuntos": ["assunto", "tarefa", "prazo", "dashboard"],
    "notifications": ["notification", "notific"]
}

def get_files_from_directory(directory, valid_exts=None, recursive=True, exclude_dirs=None):
    file_list = []
    exclude_dirs = exclude_dirs or []
    if recursive:
        for root, dirs, files in os.walk(directory):
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

def sanitize_filename(name):
    valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
    sanitized = ''.join(c if c in valid_chars else '_' for c in name)
    return sanitized.replace(' ', '_')

def extract_blocks_from_file(file_path):
    """
    Extrai blocos delimitados por:
      #BEGIN <nome_do_bloco>
      ... conteúdo ...
      #END <nome_do_bloco>
    Retorna uma lista de dicionários com chaves:
      'file', 'block_name', 'content', 'start_line' e 'end_line'
    """
    blocks = []
    block_start_re = re.compile(r'^\s*#\s*BEGIN\s+(.*)$', re.IGNORECASE)
    block_end_re = re.compile(r'^\s*#\s*END\s+(.*)$', re.IGNORECASE)
    current_block = None
    current_lines = []
    start_line = None

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, start=1):
                m_start = block_start_re.match(line)
                m_end = block_end_re.match(line)
                if m_start:
                    if current_block is not None:
                        blocks.append({
                            'file': file_path,
                            'block_name': current_block,
                            'content': ''.join(current_lines),
                            'start_line': start_line,
                            'end_line': i - 1
                        })
                    current_block = m_start.group(1).strip()
                    current_lines = []
                    start_line = i
                elif m_end and current_block is not None:
                    end_block_name = m_end.group(1).strip()
                    if end_block_name.lower() == current_block.lower():
                        blocks.append({
                            'file': file_path,
                            'block_name': current_block,
                            'content': ''.join(current_lines),
                            'start_line': start_line,
                            'end_line': i
                        })
                        current_block = None
                        current_lines = []
                        start_line = None
                    else:
                        print(f"Aviso: Inconsistência em {file_path} na linha {i}: esperado '#END {current_block}', mas encontrado '#END {end_block_name}'.")
                elif current_block is not None:
                    current_lines.append(line)
    except Exception as e:
        print(f"Erro ao ler {file_path}: {e}")
    return blocks

def filter_blocks(blocks, keywords):
    """Retorna somente os blocos cujo nome contenha alguma das keywords (case-insensitive)."""
    filtered = []
    for block in blocks:
        name = block['block_name'].lower()
        if any(kw.lower() in name for kw in keywords):
            filtered.append(block)
    return filtered

def determine_group(block_name):
    """Determina o grupo para um bloco a partir do nome, usando GROUP_MAPPING."""
    lower_name = block_name.lower()
    for group, kws in GROUP_MAPPING.items():
        for kw in kws:
            if kw.lower() in lower_name:
                return group
    return None

def file_contains_keywords(file_path, keywords):
    """Verifica se o conteúdo do arquivo contém alguma das keywords."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().lower()
            return any(kw.lower() in content for kw in keywords)
    except Exception as e:
        print(f"Erro ao ler {file_path}: {e}")
        return False

def search_related_files(group, search_dirs, valid_exts, exclude_dirs):
    """
    Procura em search_dirs arquivos cujo nome contenha ao menos uma das palavras-chave do grupo.
    Se o arquivo for genérico (ex.: models.py ou forms.py), verifica também seu conteúdo.
    Retorna uma lista de caminhos.
    """
    related_files = []
    keywords = GROUP_MAPPING.get(group, [])
    for d in search_dirs:
        if os.path.isdir(d):
            files = get_files_from_directory(d, valid_exts=valid_exts, recursive=True, exclude_dirs=exclude_dirs)
            for f in files:
                basename = os.path.basename(f).lower()
                if any(kw.lower() in basename for kw in keywords):
                    if f not in related_files:
                        related_files.append(f)
                elif basename in GENERIC_FILES:
                    if file_contains_keywords(f, keywords) and f not in related_files:
                        related_files.append(f)
        elif os.path.isfile(d):
            basename = os.path.basename(d).lower()
            if any(kw.lower() in basename for kw in keywords):
                if d not in related_files:
                    related_files.append(d)
            elif basename in GENERIC_FILES:
                if file_contains_keywords(d, keywords) and d not in related_files:
                    related_files.append(d)
    return related_files

def read_file_content(file_path, keywords=None):
    """
    Lê o conteúdo do arquivo.
    Se o arquivo for genérico (models.py ou forms.py) e keywords forem fornecidas,
    extrai somente os blocos delimitados que contenham as keywords; se nenhum bloco for encontrado, retorna uma string vazia.
    """
    try:
        basename = os.path.basename(file_path).lower()
        if basename in GENERIC_FILES and keywords:
            blocks = extract_blocks_from_file(file_path)
            filtered = filter_blocks(blocks, keywords)
            combined = "\n".join(b['content'] for b in filtered)
            return combined  # Pode ser vazio se nenhum bloco corresponder
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Erro ao ler {file_path}: {e}"

def write_combined_output(output_file, route_block, related_files, group=None):
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write("==== BLOCO DE ROTAS EXTRAÍDO ====\n")
        out.write(f"Arquivo: {route_block['file']}\n")
        out.write(f"Bloco: {route_block['block_name']} (Linhas {route_block['start_line']} a {route_block['end_line']})\n")
        out.write("=" * 80 + "\n\n")
        out.write(route_block['content'])
        out.write("\n" + "=" * 80 + "\n\n")
        if related_files:
            out.write("==== ARQUIVOS RELACIONADOS ====\n\n")
            seen = set()  # Para evitar duplicações
            for f in related_files:
                if f in seen:
                    continue
                seen.add(f)
                out.write(f"-- Arquivo: {f} --\n")
                basename = os.path.basename(f).lower()
                if group and basename in GENERIC_FILES:
                    content = read_file_content(f, GROUP_MAPPING.get(group, []))
                else:
                    content = read_file_content(f)
                out.write(content)
                out.write("\n" + "-" * 80 + "\n\n")
        else:
            out.write("Nenhum arquivo relacionado encontrado.\n")
    print(f"Saída combinada salva em: {output_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Extrai blocos de rotas (delimitados por '#BEGIN' e '#END') e agrupa com arquivos relacionados (templates, models, forms)."
    )
    parser.add_argument('--routes', required=True, help="Arquivo ou diretório de rotas (ex.: app/routes.py)")
    parser.add_argument('--templates', nargs='+', required=True, help="Diretórios ou arquivos de templates (ex.: app/templates)")
    parser.add_argument('--models', nargs='+', required=True, help="Arquivos de models (ex.: app/models.py)")
    parser.add_argument('--forms', nargs='+', required=True, help="Arquivos de forms (ex.: app/forms.py)")
    parser.add_argument('--exts', nargs='+', default=['.py', '.html'], help="Extensões válidas")
    parser.add_argument('--exclude', nargs='+', default=['__pycache__', '.git', 'venv'], help="Diretórios a excluir")
    parser.add_argument('--output_dir', default='extracted_routes_with_related', help="Diretório de saída")
    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # Processa os arquivos de rotas
    route_files = []
    if os.path.isfile(args.routes):
        route_files.append(args.routes)
    elif os.path.isdir(args.routes):
        route_files.extend(get_files_from_directory(args.routes, valid_exts=[ext.lower() for ext in args.exts], recursive=True, exclude_dirs=args.exclude))
    route_files = list(set(route_files))
    all_route_blocks = []
    for f in route_files:
        all_route_blocks.extend(extract_blocks_from_file(f))
    # Filtra blocos cujo nome contenha "rota" ou "rotas"
    route_keywords = ['rota', 'rotas']
    route_blocks = [b for b in all_route_blocks if any(kw in b['block_name'].lower() for kw in route_keywords)]
    if not route_blocks:
        print("Nenhum bloco de rota encontrado.")
        return

    # Define os diretórios/arquivos para busca de arquivos relacionados
    related_dirs = {
        "templates": args.templates,
        "models": args.models,
        "forms": args.forms
    }
    valid_exts_templates = ['.html']
    valid_exts_py = ['.py']

    # Para cada bloco de rota, determina o grupo e busca arquivos relacionados
    for index, block in enumerate(route_blocks, start=1):
        group = determine_group(block['block_name'])
        related = []
        if group:
            related.extend(search_related_files(group, related_dirs["templates"], valid_exts_templates, args.exclude))
            related.extend(search_related_files(group, related_dirs["models"], valid_exts_py, args.exclude))
            related.extend(search_related_files(group, related_dirs["forms"], valid_exts_py, args.exclude))
            # Adiciona manualmente arquivos extras conforme o grupo, evitando duplicatas:
            if group == "contabilidade":
                acc_routes = "app/accounting/routes.py"
                if os.path.exists(acc_routes) and acc_routes not in related:
                    related.append(acc_routes)
            if group == "notifications":
                base_template = "app/templates/base.html"
                if os.path.exists(base_template) and base_template not in related:
                    related.append(base_template)
        sanitized_name = sanitize_filename(block['block_name'])
        output_file = os.path.join(args.output_dir, f"block_{index}_{sanitized_name}.txt")
        write_combined_output(output_file, block, related, group)

if __name__ == '__main__':
    main()
