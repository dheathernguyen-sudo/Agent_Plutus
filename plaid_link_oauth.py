#!/usr/bin/env python3
"""
plaid_link_oauth.py — Link OAuth institutions via Plaid with ngrok HTTPS tunnel
================================================================================
For institutions that require OAuth (Fidelity, Schwab, etc.), Plaid production
needs an HTTPS redirect URI. This script uses ngrok to create a temporary tunnel.

Usage:
    python plaid_link_oauth.py fidelity
    python plaid_link_oauth.py schwab
"""

import json
import sys
import time
import threading
from pathlib import Path

CONFIG_DIR = Path.home() / ".portfolio_extract"
CONFIG_FILE = CONFIG_DIR / "config.json"

INSTITUTION_LABELS = {
    "fidelity": "Fidelity",
    "schwab": "Charles Schwab",
    "merrill": "Merrill Lynch (Bank of America)",
}


def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2))
    print(f"  Config saved.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python plaid_link_oauth.py <institution>")
        print(f"  Available: {', '.join(INSTITUTION_LABELS.keys())}")
        sys.exit(1)

    label = sys.argv[1].lower()
    if label not in INSTITUTION_LABELS:
        print(f"  Unknown institution: {label}")
        sys.exit(1)

    name = INSTITUTION_LABELS[label]

    # Load config
    config = load_config()
    pc = config.get("plaid", {})
    if not pc.get("client_id") or not pc.get("secret"):
        print("  ERROR: Plaid credentials not configured.")
        sys.exit(1)

    # Import Plaid
    try:
        import plaid
        from plaid.api import plaid_api
        from plaid.model.country_code import CountryCode
        from plaid.model.products import Products
        from plaid.model.link_token_create_request import LinkTokenCreateRequest
        from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
        from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
        from plaid.model.accounts_get_request import AccountsGetRequest
    except ImportError:
        print("  ERROR: pip install plaid-python")
        sys.exit(1)

    # Create Plaid client
    env_map = {"sandbox": plaid.Environment.Sandbox, "production": plaid.Environment.Production}
    configuration = plaid.Configuration(
        host=env_map.get(pc.get("environment", "production"), plaid.Environment.Production),
        api_key={"clientId": pc["client_id"], "secret": pc["secret"], "plaidVersion": "2020-09-14"},
    )
    client = plaid_api.PlaidApi(plaid.ApiClient(configuration))

    # Start ngrok tunnel
    print(f"\n  Starting ngrok HTTPS tunnel...")
    from pyngrok import ngrok
    tunnel = ngrok.connect(8234, "http")
    ngrok_url = tunnel.public_url
    redirect_uri = f"{ngrok_url}/oauth-callback"
    print(f"  Tunnel: {ngrok_url}")
    print(f"  Redirect URI: {redirect_uri}")

    # Create link token with HTTPS redirect
    print(f"\n  Creating Plaid link token for {name}...")
    req = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=f"portfolio-{label}"),
        client_name="Portfolio Analyzer",
        products=[Products("investments")],
        country_codes=[CountryCode("US")],
        language="en",
        redirect_uri=redirect_uri,
    )
    link_token = client.link_token_create(req)["link_token"]
    print(f"  Link token created.")

    # Start Flask server
    from flask import Flask, request as fr, jsonify
    app = Flask(__name__)
    result = {"token": None, "done": False}

    html = f"""<!DOCTYPE html><html><head><title>Link {name}</title>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<style>body{{font-family:sans-serif;max-width:500px;margin:80px auto;text-align:center}}
button{{padding:12px 32px;font-size:16px;background:#1a73e8;color:white;border:none;border-radius:6px;cursor:pointer}}
#s{{margin-top:20px;padding:16px;border-radius:8px;display:none}}
.ok{{background:#e8f5e9;color:#2e7d32}}.err{{background:#fce4ec;color:#c62828}}</style></head>
<body><h1>Link {name}</h1>
<button id="b" onclick="handler.open()">Connect</button><div id="s"></div>
<script>
const handler=Plaid.create({{token:'{link_token}',
onSuccess:(t,m)=>{{
  document.getElementById('s').className='ok';
  document.getElementById('s').style.display='block';
  document.getElementById('s').textContent='Success! Linking account...';
  document.getElementById('b').style.display='none';
  fetch('/cb',{{method:'POST',headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{public_token:t}})}})
  .then(()=>document.getElementById('s').textContent='Done! You can close this tab.')
  .catch(e=>document.getElementById('s').textContent='Error: '+e);
}},
onExit:(e,m)=>{{
  console.log('onExit',e,m);
  if(e){{let s=document.getElementById('s');s.style.display='block';
    s.className='err';s.textContent='Error: '+(e.display_message||e.error_message||JSON.stringify(e));}}
}},
receivedRedirectUri:window.location.href.includes('oauth_state_id')?window.location.href:null
}});
</script></body></html>"""

    @app.route("/")
    def index():
        return html

    @app.route("/oauth-callback")
    def oauth_callback():
        """Handle OAuth redirect — serve page that resumes Plaid Link."""
        oauth_state_id = fr.args.get("oauth_state_id")
        print(f"  OAuth callback received (state: {oauth_state_id[:20] if oauth_state_id else '?'}...)")

        # Create a new link token to resume
        resume_req = LinkTokenCreateRequest(
            user=LinkTokenCreateRequestUser(client_user_id=f"portfolio-{label}"),
            client_name="Portfolio Analyzer",
            products=[Products("investments")],
            country_codes=[CountryCode("US")],
            language="en",
            redirect_uri=redirect_uri,
        )
        resume_token = client.link_token_create(resume_req)["link_token"]

        # Serve page with receivedRedirectUri so Plaid Link resumes the OAuth flow
        resume_html = f"""<!DOCTYPE html><html><head><title>Link {name}</title>
<script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
<style>body{{font-family:sans-serif;max-width:500px;margin:80px auto;text-align:center}}
#s{{margin-top:20px;padding:16px;border-radius:8px;display:none}}
.ok{{background:#e8f5e9;color:#2e7d32}}</style></head>
<body><h1>Completing {name} Link...</h1><div id="s"></div>
<script>
const handler=Plaid.create({{token:'{resume_token}',
onSuccess:(t,m)=>{{
  document.getElementById('s').className='ok';
  document.getElementById('s').style.display='block';
  document.getElementById('s').textContent='Success! Linking account...';
  fetch('/cb',{{method:'POST',headers:{{'Content-Type':'application/json'}},
  body:JSON.stringify({{public_token:t}})}})
  .then(()=>document.getElementById('s').textContent='Done! You can close this tab.')
  .catch(e=>document.getElementById('s').textContent='Error: '+e);
}},
onExit:(e,m)=>{{if(e){{let s=document.getElementById('s');s.style.display='block';
  s.style.background='#fce4ec';s.style.color='#c62828';
  s.textContent='Error: '+(e.display_message||e.error_message||JSON.stringify(e));}}}},
receivedRedirectUri:window.location.href
}});
handler.open();
</script></body></html>"""
        return resume_html

    @app.route("/cb", methods=["POST"])
    def cb():
        result["token"] = fr.get_json().get("public_token")
        result["done"] = True
        print(f"  Public token received!")
        return jsonify({"ok": True})

    # Run server in background
    def run_server():
        app.run(port=8234, debug=False, use_reloader=False, threaded=True)

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    import webbrowser
    print(f"\n  Opening browser at {ngrok_url}")
    print(f"  Complete the {name} login in the browser.")
    print(f"  Waiting up to 5 minutes...\n")
    webbrowser.open(ngrok_url)

    # Wait for token
    for _ in range(300):
        if result["done"]:
            break
        time.sleep(1)

    # Cleanup ngrok
    ngrok.disconnect(tunnel.public_url)
    ngrok.kill()

    if not result["token"]:
        print(f"\n  No token received. Linking failed.")
        sys.exit(1)

    # Exchange public token for access token
    print(f"\n  Exchanging token...")
    ex = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=result["token"])
    )
    access_token = ex["access_token"]
    item_id = ex["item_id"]

    # Get accounts
    accts = [
        {"account_id": a["account_id"], "name": a["name"],
         "type": str(a["type"]), "subtype": str(a.get("subtype") or ""), "mask": a.get("mask")}
        for a in client.accounts_get(AccountsGetRequest(access_token=access_token))["accounts"]
    ]

    # Save to config
    pc.setdefault("institutions", {})[label] = {
        "access_token": access_token,
        "item_id": item_id,
        "accounts": accts,
    }
    config["plaid"] = pc
    save_config(config)

    print(f"\n  Linked {name}: {len(accts)} accounts")
    for a in accts:
        print(f"    - {a['name']} ({a['type']}/{a['subtype']}) mask:{a.get('mask', '?')}")

    print(f"\n  Done!")


if __name__ == "__main__":
    main()
