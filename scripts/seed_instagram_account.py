"""One-off: copies the legacy global Instagram credentials from the environment
(INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_BUSINESS_ACCOUNT_ID) into the
instagram_accounts table for one company. Idempotent (skips if a row exists).

    ssh -i ~/.ssh/qars_vps ubuntu@46.8.194.222 \
      "cd /home/ubuntu/ai-office && docker compose exec -T api python3 - 2 qarsfastfood" \
      < scripts/seed_instagram_account.py

Arguments: <company_id> [username]. token_refreshed_at is backdated to the real
issue date so the support loop refreshes the token on its first pass.
"""
import sys
from datetime import datetime

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.instagram_account import InstagramAccount

company_id = int(sys.argv[1])
username = sys.argv[2] if len(sys.argv) > 2 else None

if not settings.INSTAGRAM_ACCESS_TOKEN or not settings.INSTAGRAM_BUSINESS_ACCOUNT_ID:
    raise SystemExit("INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_BUSINESS_ACCOUNT_ID are not set in the environment")

db = SessionLocal()
company = db.query(Company).filter(Company.id == company_id).first()
if company is None:
    raise SystemExit(f"company {company_id} not found")

if db.query(InstagramAccount).filter(InstagramAccount.company_id == company_id).first():
    print(f"company {company_id} already has an Instagram account row, nothing to do")
else:
    db.add(
        InstagramAccount(
            company_id=company_id,
            account_id=settings.INSTAGRAM_BUSINESS_ACCOUNT_ID,
            username=username,
            access_token=settings.INSTAGRAM_ACCESS_TOKEN,
            token_refreshed_at=datetime(2026, 8, 13),
        )
    )
    db.commit()
    print(f"seeded Instagram account for company {company_id} ({company.name}), account_id={settings.INSTAGRAM_BUSINESS_ACCOUNT_ID}")
