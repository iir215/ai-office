"""Prints a one-hour link that connects an Instagram account to a company.
Whoever opens it logs in to Instagram and approves; the callback on our server
saves the token for that company.

    ssh -i ~/.ssh/qars_vps ubuntu@46.8.194.222 \
      "cd /home/ubuntu/ai-office && docker compose exec -T api python3 - 6" \
      < scripts/instagram_connect_link.py

Prerequisites in the Meta app (developers.facebook.com): the Instagram account
must be added as an Instagram Tester (and accept the invite in Instagram), and
the redirect URI printed below must be listed under Instagram API with
Instagram Login -> Business login settings -> OAuth redirect URIs.
"""
import sys

from app.api.v1.instagram_oauth import build_connect_url, redirect_uri
from app.db.session import SessionLocal
from app.models.company import Company

company_id = int(sys.argv[1])
db = SessionLocal()
company = db.query(Company).filter(Company.id == company_id).first()
if company is None:
    raise SystemExit(f"company {company_id} not found")

print(f"Company: {company.name} (id={company.id})")
print(f"Redirect URI to whitelist in the Meta app: {redirect_uri()}")
print("Connect link (valid 60 minutes):")
print(build_connect_url(company_id))
