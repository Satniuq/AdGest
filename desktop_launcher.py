import threading
import webview
from app import create_app

app = create_app()

def run_flask():
    print("A iniciar Flask…")
    app.run(debug=False, port=5000)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    print("A abrir janela desktop…")
    webview.create_window("AdGest", "http://127.0.0.1:5000")
    webview.start()   # ESTA LINHA É OBRIGATÓRIA!
