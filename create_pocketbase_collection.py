"""
MercadoFácil Costa Rica - Script de Provisión de Colecciones en PocketBase
Crea automáticamente las colecciones 'telemetry_sessions' (con las 23 métricas de telemetría)
y 'visitor_logs' en https://pb-mercadofacil.webticocr.com usando la API de Superuser.

Uso:
  python create_pocketbase_collection.py
  python create_pocketbase_collection.py --password "TU_PASSWORD"
  python create_pocketbase_collection.py --email "corea3000@gmail.com" --password "TU_PASSWORD"
"""

import sys
import json
import argparse
import getpass
import urllib.request
import urllib.error

DEFAULT_URL = "https://pb-mercadofacil.webticocr.com"
DEFAULT_EMAIL = "corea3000@gmail.com"

TELEMETRY_SESSION_FIELDS = [
    {"name": "session_id", "type": "text", "required": True, "max": 64},
    {"name": "session_token", "type": "text", "max": 64},
    {"name": "started_at", "type": "date", "required": True},
    {"name": "dwell_seconds", "type": "number", "min": 0},
    {"name": "is_logged", "type": "bool"},
    {"name": "user_id", "type": "text", "max": 50},
    {"name": "user_email", "type": "text", "max": 120},
    {"name": "referrer", "type": "text", "max": 255},
    {"name": "location", "type": "text", "max": 100},
    {"name": "device_type", "type": "text", "max": 20},
    {"name": "os", "type": "text", "max": 50},
    {"name": "browser", "type": "text", "max": 50},
    {"name": "resolution", "type": "text", "max": 20},
    {"name": "filter_history", "type": "json"},
    {"name": "search_terms", "type": "json"},
    {"name": "language", "type": "text", "max": 2},
    {"name": "language_history", "type": "json"},
    {"name": "grid_page_size", "type": "number"},
    {"name": "grid_max_page", "type": "number"},
    {"name": "grid_page_changes", "type": "number"},
    {"name": "selected_super", "type": "text", "max": 50},
    {"name": "selected_category", "type": "text", "max": 100},
    {"name": "cart_last_product", "type": "text", "max": 100},
    {"name": "cart_add_count", "type": "number"},
    {"name": "cart_value", "type": "number"},
    {"name": "cart_limit_reached", "type": "bool"},
    {"name": "cta_clicks", "type": "json"},
    {"name": "viewed_business", "type": "bool"},
    {"name": "renew_click_at", "type": "date"},
    {"name": "grid_latency_ms", "type": "number"},
    {"name": "grid_latency_avg_ms", "type": "number"},
]

VISITOR_LOGS_FIELDS = [
    {"name": "session_id", "type": "text", "required": True, "max": 64},
    {"name": "is_logged", "type": "bool"},
    {"name": "user_email", "type": "text"},
    {"name": "user_name", "type": "text"},
    {"name": "event_type", "type": "text", "required": True, "max": 50},
    {"name": "details", "type": "text"},
    {"name": "device_info", "type": "text"},
    {"name": "language", "type": "text", "max": 20},
    {"name": "referrer", "type": "text"},
]


def request_json(url, method="GET", headers=None, data=None):
    hdrs = {"User-Agent": "MercadoFacilProvisioner/1.0"}
    if headers:
        hdrs.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as err:
        content = err.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw": content}
        return err.code, parsed


def authenticate_superuser(base_url, identity, password):
    url = f"{base_url.rstrip('/')}/api/collections/_superusers/auth-with-password"
    status, res = request_json(url, method="POST", data={"identity": identity, "password": password})
    if status == 200 and "token" in res:
        return res["token"]
    legacy_url = f"{base_url.rstrip('/')}/api/admins/auth-with-password"
    status_leg, res_leg = request_json(legacy_url, method="POST", data={"identity": identity, "password": password})
    if status_leg == 200 and "token" in res_leg:
        return res_leg["token"]
    raise RuntimeError(f"Error de autenticación ({status}): {res}")


def ensure_collection(base_url, token, name, fields, rules):
    chk_url = f"{base_url.rstrip('/')}/api/collections/{name}"
    headers = {"Authorization": token}
    status, res = request_json(chk_url, method="GET", headers=headers)
    if status == 200:
        print(f"  [OK] La colección '{name}' ya existe en PocketBase.")
        return res

    print(f"  [+] Creando colección '{name}' en PocketBase...")
    create_url = f"{base_url.rstrip('/')}/api/collections"
    payload = {
        "name": name,
        "type": "base",
        "fields": fields,
        "listRule": rules.get("listRule", "@request.auth.admin = true"),
        "viewRule": rules.get("viewRule", "@request.auth.admin = true"),
        "createRule": rules.get("createRule", ""),  # Vacio = publico (anónimos y logueados pueden enviar telemetría)
        "updateRule": rules.get("updateRule", ""),
        "deleteRule": rules.get("deleteRule", "@request.auth.admin = true"),
    }
    status_create, res_create = request_json(create_url, method="POST", headers=headers, data=payload)
    if status_create in (200, 201):
        print(f"  [EXITO] Colección '{name}' creada exitosamente!")
        return res_create
    else:
        raise RuntimeError(f"Fallo al crear '{name}' ({status_create}): {res_create}")


def main():
    parser = argparse.ArgumentParser(description="Provisionador de colecciones PocketBase para MercadoFácil")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"URL base de PocketBase (default: {DEFAULT_URL})")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help=f"Email superuser (default: {DEFAULT_EMAIL})")
    parser.add_argument("--password", default=None, help="Contraseña del superuser")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    identity = args.email
    password = args.password

    print("=" * 60)
    print("MERCADOFÁCIL COSTA RICA - PROVISIÓN POCKETBASE")
    print(f"Destino:  {base_url}")
    print(f"Usuario:  {identity}")
    print("=" * 60)

    if not password:
        password = getpass.getpass(f"Ingresa la contraseña para {identity}: ")

    print("\n1. Autenticando como Superuser...")
    try:
        token = authenticate_superuser(base_url, identity, password)
        print("   [OK] Autenticado exitosamente.")
    except Exception as e:
        print(f"   [ERROR] No se pudo autenticar: {e}")
        sys.exit(1)

    print("\n2. Provisionando 'telemetry_sessions' (23 métricas)...")
    try:
        ensure_collection(
            base_url,
            token,
            "telemetry_sessions",
            TELEMETRY_SESSION_FIELDS,
            {
                "listRule": "@request.auth.admin = true",
                "viewRule": "@request.auth.admin = true",
                "createRule": "",
                "updateRule": "",
                "deleteRule": "@request.auth.admin = true",
            },
        )
    except Exception as e:
        print(f"   [ERROR] {e}")

    print("\n3. Provisionando 'visitor_logs'...")
    try:
        ensure_collection(
            base_url,
            token,
            "visitor_logs",
            VISITOR_LOGS_FIELDS,
            {
                "listRule": "@request.auth.admin = true",
                "viewRule": "@request.auth.admin = true",
                "createRule": "",
                "updateRule": "@request.auth.admin = true",
                "deleteRule": "@request.auth.admin = true",
            },
        )
    except Exception as e:
        print(f"   [ERROR] {e}")

    print("\n" + "=" * 60)
    print("Proceso completado. Actualiza tu panel de PocketBase para ver las colecciones.")
    print("=" * 60)


if __name__ == "__main__":
    main()
