"""
MercadoFácil Costa Rica - Servidor Local y API de Scraping en Vivo
Ejecuta la aplicación web y provee endpoints REST y SSE (Server-Sent Events) para:
- GET / : Sirve index.html
- GET /data/products.json : Retorna el catálogo de precios scrapeados
- GET /api/products : Retorna el JSON de productos reales
- GET /api/scrape/stream : Ejecuta scraper.py en tiempo real y transmite los URLs y precios
"""

import http.server
import socketserver
import json
import os
import sys
import threading
import time
from datetime import datetime
import scraper

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class MercadoFacilHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        # 1. API: Obtener productos reales actuales
        if self.path == '/api/products':
            self.handle_get_products()
            return
            
        # 2. API: Iniciar Scraping en Vivo con Server-Sent Events (SSE)
        elif self.path == '/api/scrape/stream':
            self.handle_scrape_stream()
            return

        # 3. Servir archivos estáticos estándar (index.html, data/products.json, etc.)
        super().do_GET()

    def handle_get_products(self):
        json_path = os.path.join(BASE_DIR, 'data', 'products.json')
        if not os.path.exists(json_path):
            # Si no existe, ejecutar scraper inicial
            scraper.run_full_scraper()
            
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
        except Exception as e:
            self.send_error(500, f"Error reading products: {e}")

    def handle_scrape_stream(self):
        """Transmite en vivo los eventos de scraping vía Server-Sent Events (SSE)."""
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # Enviar evento inicial
        init_event = json.dumps({
            'type': 'start',
            'message': 'Iniciando conexión con los portales de Walmart, MásxMenos, Maxi Palí, Palí y Auto Mercado...',
            'timestamp': datetime.now().isoformat()
        })
        self.wfile.write(f"data: {init_event}\n\n".encode('utf-8'))
        self.wfile.flush()

        counter = 0

        def on_item_scraped(item, res):
            nonlocal counter
            counter += 1
            event_payload = json.dumps({
                'type': 'item',
                'super': item['super'],
                'item': item['item'],
                'product_title': item['product_title'],
                'precio': item['precio'],
                'url': item['url'],
                'target_url': res.get('url', item['url']),
                'statusCode': res.get('statusCode', 200),
                'latencyMs': res.get('latencyMs', 45),
                'index': counter,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }, ensure_ascii=False)
            
            try:
                self.wfile.write(f"data: {event_payload}\n\n".encode('utf-8'))
                self.wfile.flush()
            except Exception:
                pass

        try:
            # Ejecutar el scraper real
            products = scraper.run_full_scraper(on_item_scraped=on_item_scraped)
            
            # Enviar evento de finalización
            done_event = json.dumps({
                'type': 'done',
                'total': len(products),
                'message': f"Scraping en vivo completado con {len(products)} productos reales actualizados.",
                'timestamp': datetime.now().isoformat()
            })
            self.wfile.write(f"data: {done_event}\n\n".encode('utf-8'))
            self.wfile.flush()
        except Exception as err:
            err_event = json.dumps({'type': 'error', 'message': str(err)})
            try:
                self.wfile.write(f"data: {err_event}\n\n".encode('utf-8'))
                self.wfile.flush()
            except Exception:
                pass


def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), MercadoFacilHandler) as httpd:
        print("\n" + "=" * 70)
        print(f" 🌐 SERVIDOR MERCADOFÁCIL INICIADO EN:")
        print(f"    http://localhost:{PORT}")
        print(f"    http://127.0.0.1:{PORT}")
        print("=" * 70)
        print(" Presione Ctrl+C para detener el servidor.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n Servidor detenido.")


if __name__ == '__main__':
    run_server()
