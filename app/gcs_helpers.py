# app/gcs_helpers.py

from google.cloud import storage
from flask import current_app

def upload_to_gcs(file_obj, filename, content_type):
    """
    Faz o upload do arquivo para o bucket do Google Cloud Storage.
    
    Parâmetros:
      - file_obj: Objeto do arquivo (tipo FileStorage)
      - filename: Nome seguro do arquivo
      - content_type: Tipo MIME do arquivo
      
    Retorna:
      - A URL pública do arquivo após o upload.
    """
    # Instancia o cliente do Storage
    storage_client = storage.Client()
    
    # Recupera o nome do bucket a partir da configuração da aplicação
    bucket_name = current_app.config.get('GCS_BUCKET_NAME')  # Ex.: "user_imag"
    bucket = storage_client.bucket(bucket_name)
    
    # Cria um blob (objeto) com o nome desejado
    blob = bucket.blob(filename)
    
    # Faz o upload do arquivo
    blob.upload_from_file(file_obj, content_type=content_type)
    
    # Torna o objeto público; se preferir, você pode gerar uma URL assinada para acesso controlado
    blob.make_public()
    
    return blob.public_url
