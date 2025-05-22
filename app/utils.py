# app/utils.py
import unicodedata

def normalize_header(header: str) -> str:
    """
    Remove acentuação e espaço em branco de um cabeçalho de CSV,
    colocando tudo em minúsculas.
    """
    header = header.strip().lower()
    return unicodedata.normalize('NFKD', header) \
                      .encode('ASCII', 'ignore') \
                      .decode('utf-8')
