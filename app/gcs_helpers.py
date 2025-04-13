from google.cloud import storage
from flask import current_app

def upload_to_gcs(file_obj, filename, content_type):
    try:
        storage_client = storage.Client()
        bucket_name = current_app.config.get('GCS_BUCKET_NAME')
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_file(file_obj, content_type=content_type)
        # Com uniform bucket-level access ativado e o bucket configurado para acesso público via IAM,
        # não é necessário (e nem permitido) usar blob.make_public().
        current_app.logger.info(f"Upload realizado com sucesso para o bucket {bucket_name}. URL: {blob.public_url}")
        return blob.public_url
    except Exception as e:
        current_app.logger.error("Erro no upload para o GCS", exc_info=True)
        raise
