import httpx

from app.core.config import settings

SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


def web_search(query: str, num_results: int = 5) -> str:
    if not settings.BRAVE_SEARCH_API_KEY:
        return "Web search is not configured."

    resp = httpx.get(
        SEARCH_URL,
        params={"q": query, "count": num_results},
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": settings.BRAVE_SEARCH_API_KEY,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        return f"Search failed: {resp.status_code} {resp.text[:200]}"

    results = resp.json().get("web", {}).get("results", [])
    if not results:
        return "No results found."

    lines = []
    for item in results:
        title = item.get("title", "")
        link = item.get("url", "")
        snippet = item.get("description", "")
        lines.append(f"- {title}\n  {link}\n  {snippet}")

    return "\n".join(lines)
