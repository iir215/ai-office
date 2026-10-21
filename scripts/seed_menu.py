"""Loads the Bonch burgers menu (approved by the owner on 2026-10-05, prices in UZS) into
menu_items for the ordering Mini App. Idempotent: matches by (company, category, name), so
re-running updates prices/descriptions instead of duplicating. To change the menu, edit MENU
and run:

    ssh -i ~/.ssh/qars_vps ubuntu@46.8.194.222 \
      "cd /home/ubuntu/ai-office && docker compose exec -T api python3 -" < scripts/seed_menu.py
"""
from app.db.session import SessionLocal
from app.models.company import Company
from app.models.menu_item import MenuItem

COMPANY_ID = 2

# (category, name, name_uz, description, description_uz, price)
MENU = [
    ("Бургеры", "Классик", "Klassik", "Говяжья котлета, салат, томат, лук, соус", "Mol go‘shti kotleti, salat, pomidor, piyoz, sous", 30000),
    ("Бургеры", "Чизбургер", "Chizburger", "Говяжья котлета, сыр, салат, томат, лук, соус", "Mol go‘shti kotleti, pishloq, salat, pomidor, piyoz, sous", 35000),
    ("Бургеры", "Двойной чизбургер", "Ikkita kotletli chizburger", "Две говяжьи котлеты, сыр, салат, томат, лук, соус", "Ikkita mol go‘shti kotleti, pishloq, salat, pomidor, piyoz, sous", 45000),
    ("Бургеры", "Чикен бургер", "Chiken burger", "Куриная котлета, салат, томат, соус", "Tovuq kotleti, salat, pomidor, sous", 28000),
    ("French hotdog", "Френч классик", "Frensh klassik", "Сосиска, кетчуп, горчица, маринованный огурец, лук", "Sosiska, ketchup, xantal, tuzlangan bodring, piyoz", 15000),
    ("French hotdog", "Френч чиз", "Frensh chiz", "Сосиска, сырный соус, сыр, лук, маринованный огурец", "Sosiska, pishloqli sous, pishloq, piyoz, tuzlangan bodring", 20000),
    ("French hotdog", "Хантер дог", "Hanter dog", "Сосиска, BBQ соус, маринованный огурец, лук", "Sosiska, BBQ sous, tuzlangan bodring, piyoz", 25000),
    ("French hotdog", "Спайси дог", "Spicy dog", "Сосиска, острый соус, халапеньо, лук, маринованный огурец", "Sosiska, achchiq sous, halapenyo, piyoz, tuzlangan bodring", 20000),
    ("Картофель фри", "Картофель фри маленький", "Kartoshka fri (kichik)", "Хрустящий, золотистый", "Qarsildoq, tillarang", 10000),
    ("Картофель фри", "Картофель фри средний", "Kartoshka fri (o‘rta)", "Хрустящий, золотистый", "Qarsildoq, tillarang", 15000),
    ("Картофель фри", "Картофель фри большой", "Kartoshka fri (katta)", "Хрустящий, золотистый", "Qarsildoq, tillarang", 20000),
    ("Наггетсы и крылья", "Наггетсы (4 шт.)", "Naggetslar (4 dona)", "С нашими соусами", "Bizning souslar bilan", 20000),
    ("Наггетсы и крылья", "Крылья (4 шт.)", "Qanotchalar (4 dona)", "С нашими соусами", "Bizning souslar bilan", 25000),
    ("Соусы", "Кетчуп", "Ketchup", None, None, 5000),
    ("Соусы", "Майонез", "Mayonez", None, None, 5000),
    ("Соусы", "Сырный соус", "Pishloqli sous", None, None, 5000),
    ("Соусы", "BBQ соус", "BBQ sous", None, None, 5000),
    ("Соусы", "Чесночный соус", "Sarimsoqli sous", None, None, 5000),
    ("Соусы", "Острый соус", "Achchiq sous", None, None, 5000),
    ("Молочные коктейли", "Коктейль ванильный", "Vanilli kokteyl", None, None, 20000),
    ("Молочные коктейли", "Коктейль шоколадный", "Shokoladli kokteyl", None, None, 20000),
    ("Молочные коктейли", "Коктейль клубничный", "Qulupnayli kokteyl", None, None, 20000),
    ("Напитки", "Pepsi 0,5 л", "Pepsi 0,5 l", None, None, 12000),
    ("Напитки", "Mirinda 0,5 л", "Mirinda 0,5 l", None, None, 12000),
    ("Напитки", "7 Up 0,5 л", "7 Up 0,5 l", None, None, 12000),
    ("Напитки", "Вода 0,5 л", "Suv 0,5 l", None, None, 6000),
    ("Напитки", "Lipton холодный чай 0,5 л", "Lipton sovuq choy 0,5 l", None, None, 12000),
    ("Свежие фреши", "Фреш апельсин", "Apelsin fresh", "Натуральный", "Tabiiy", 25000),
    ("Свежие фреши", "Фреш грейпфрут", "Greypfrut fresh", "Натуральный", "Tabiiy", 30000),
    ("Свежие фреши", "Фреш гранат", "Anor fresh", "Натуральный", "Tabiiy", 35000),
    ("Свежие фреши", "Фреш яблоко", "Olma fresh", "Натуральный", "Tabiiy", 20000),
    ("Свежие фреши", "Фреш морковь", "Sabzi fresh", "Натуральный", "Tabiiy", 15000),
    ("Свежие фреши", "Фреш яблоко + морковь", "Olma + sabzi fresh", "Натуральный", "Tabiiy", 20000),
    ("Чай и кофе", "Турецкий чай (чашка)", "Turk choyi (piyola)", None, None, 5000),
    ("Чай и кофе", "Турецкий чай (чайник)", "Turk choyi (choynak)", None, None, 30000),
    ("Чай и кофе", "Чай чёрный", "Qora choy", None, None, 10000),
    ("Чай и кофе", "Чай зелёный", "Yashil choy", None, None, 10000),
    ("Чай и кофе", "Эспрессо", "Espresso", None, None, 20000),
    ("Чай и кофе", "Американо", "Americano", None, None, 25000),
    ("Чай и кофе", "Латте", "Latte", None, None, 35000),
    ("Чай и кофе", "Капучино", "Cappuccino", None, None, 30000),
]

# Pixel-art picture per item (files in backend/app/static/shop/sprites/, see make_pixel_sprites.py).
SPRITES = {
    "Классик": "burger_classic", "Чизбургер": "burger_cheese", "Двойной чизбургер": "burger_double", "Чикен бургер": "burger_chicken",
    "Френч классик": "hotdog_classic", "Френч чиз": "hotdog_cheese", "Хантер дог": "hotdog_hunter", "Спайси дог": "hotdog_spicy",
    "Картофель фри маленький": "fries_s", "Картофель фри средний": "fries_m", "Картофель фри большой": "fries_l",
    "Наггетсы (4 шт.)": "nuggets", "Крылья (4 шт.)": "wings",
    "Кетчуп": "sauce_ketchup", "Майонез": "sauce_mayo", "Сырный соус": "sauce_cheese", "BBQ соус": "sauce_bbq",
    "Чесночный соус": "sauce_garlic", "Острый соус": "sauce_hot",
    "Коктейль ванильный": "shake_vanilla", "Коктейль шоколадный": "shake_choco", "Коктейль клубничный": "shake_straw",
    "Pepsi 0,5 л": "drink_cola", "Mirinda 0,5 л": "drink_orange", "7 Up 0,5 л": "drink_lime", "Вода 0,5 л": "drink_water",
    "Lipton холодный чай 0,5 л": "drink_icetea",
    "Фреш апельсин": "juice_orange", "Фреш грейпфрут": "juice_grapefruit", "Фреш гранат": "juice_pomegranate",
    "Фреш яблоко": "juice_apple", "Фреш морковь": "juice_carrot", "Фреш яблоко + морковь": "juice_apple_carrot",
    "Турецкий чай (чашка)": "tea_cup", "Турецкий чай (чайник)": "tea_pot", "Чай чёрный": "tea_black", "Чай зелёный": "tea_green",
    "Эспрессо": "espresso", "Американо": "americano", "Латте": "latte", "Капучино": "cappuccino",
}

db = SessionLocal()
assert db.query(Company).filter(Company.id == COMPANY_ID).first(), "unknown company"
created = updated = 0
for sort, (category, name, name_uz, desc, desc_uz, price) in enumerate(MENU, start=1):
    item = (
        db.query(MenuItem)
        .filter(MenuItem.company_id == COMPANY_ID, MenuItem.category == category, MenuItem.name == name)
        .first()
    )
    if item:
        updated += 1
    else:
        item = MenuItem(company_id=COMPANY_ID, category=category, name=name)
        db.add(item)
        created += 1
    item.name_uz, item.description, item.description_uz = name_uz, desc, desc_uz
    item.price, item.sort, item.is_active = price, sort, True
    item.sprite = SPRITES.get(name)
db.commit()
print(f"menu loaded: {created} created, {updated} updated, {len(MENU)} total")
