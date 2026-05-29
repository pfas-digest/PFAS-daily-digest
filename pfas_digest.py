import os
import json
import time
import anthropic
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SENDGRID_API_KEY  = os.environ["SENDGRID_API_KEY"]
FROM_EMAIL        = os.environ.get("FROM_EMAIL", "andrew@remotevelocity.com")
TO_EMAIL          = os.environ.get("TO_EMAIL",   "andrew@remotevelocity.com")
MAX_STORIES       = int(os.environ.get("MAX_STORIES", "3"))
PAUSE_BETWEEN_TOPICS = 20  # seconds — keeps token/min usage well under the 30k limit

TOPICS = [
    {"label": "Regulation & EPA",    "icon": "🏛️", "query": "PFAS regulation EPA policy 2026"},
    {"label": "Water Contamination", "icon": "💧",  "query": "PFAS water contamination drinking water 2026"},
    {"label": "Health Research",     "icon": "🔬",  "query": "PFAS health effects research study 2026"},
    {"label": "Litigation",          "icon": "⚖️",  "query": "PFAS lawsuit litigation settlement 2026"},
    {"label": "Remediation Tech",    "icon": "♻️",  "query": "PFAS cleanup remediation technology 2026"},
    {"label": "Montana PFAS News",   "icon": "🏔️",  "query": "PFAS Montana news, sites, testing, cleanup remediation public health 2026"},
]

# ── API call with exponential backoff on rate limit ───────────────────────────
def call_with_retry(client, **kwargs):
    delays = [20, 40, 80]
    for attempt, delay in enumerate(delays, 1):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            if attempt == len(delays):
                raise
            print(f"  ⏳ Rate limit hit — waiting {delay}s (retry {attempt}/{len(delays)})…")
            time.sleep(delay)

# ── Fetch stories — two-step: search then extract ────────────────────────────
def fetch_stories(client, topic):
    print(f"  Searching: {topic['label']}…")

    # Step 1 — search the web, get natural language results
    search_resp = call_with_retry(
        client,
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": (
                f"Search for the {MAX_STORIES} most recent news stories about: {topic['query']}. "
                f"For each story provide: the full headline, source publication name, "
                f"publication date, full URL, and a 2-3 sentence factual summary."
            ),
        }],
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
    )

    # Collect all text blocks from the search response
    search_text = "\n".join(
        block.text for block in search_resp.content if block.type == "text"
    ).strip()

    if not search_text:
        print(f"  ⚠ No search text returned for '{topic['label']}'")
        return []

    # Step 2 — extract structured JSON (no tools, no web access)
    extract_resp = call_with_retry(
        client,
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=(
            "You are a data extraction assistant. "
            "Your only job is to convert news summaries into structured JSON. "
            "Return ONLY raw JSON — no markdown fences, no preamble, no explanation."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Extract exactly {MAX_STORIES} news stories from the text below.\n"
                f"Return this exact JSON structure:\n"
                f'{{"stories":[{{"headline":"...","source":"...","date":"...","url":"...","summary":"2-3 sentences"}}]}}\n\n'
                f"If fewer than {MAX_STORIES} stories are present, include all that are available.\n\n"
                f"Text:\n{search_text}"
            ),
        }],
    )

    for block in extract_resp.content:
        if block.type == "text":
            try:
                raw   = block.text.replace("```json", "").replace("```", "").strip()
                start = raw.find("{")
                end   = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    data    = json.loads(raw[start:end])
                    stories = data.get("stories", [])
                    if stories:
                        print(f"  ✓ {len(stories)} stories extracted for '{topic['label']}'")
                        return stories[:MAX_STORIES]
            except json.JSONDecodeError as e:
                print(f"  ⚠ JSON parse error for '{topic['label']}': {e}")

    print(f"  ⚠ Could not extract stories for '{topic['label']}'")
    return []

# ── Build HTML email ──────────────────────────────────────────────────────────
def build_html(sections, today):
    story_card = (
        '<div style="margin-bottom:12px;padding:12px;background:#f8f8f6;'
        'border-left:3px solid #444;border-radius:2px">'
        '<strong style="font-size:14px;display:block">{headline_link}</strong>'
        '<span style="font-size:11px;color:#888">{source}{date_part}</span>'
        '<p style="font-size:13px;color:#444;margin:6px 0 0;line-height:1.55">{summary}</p>'
        '</div>'
    )

    body_parts = []
    for section in sections:
        cards = ""
        for s in section["stories"]:
            headline  = s.get("headline", "Untitled")
            url       = s.get("url", "")
            hl_link   = (
                f'<a href="{url}" style="color:#1a1a1a;text-decoration:underline">{headline}</a>'
                if url else headline
            )
            date_part = f" · {s['date']}" if s.get("date") else ""
            cards += story_card.format(
                headline_link=hl_link,
                source=s.get("source", ""),
                date_part=date_part,
                summary=s.get("summary", ""),
            )
        body_parts.append(
            f'<div style="margin-bottom:28px">'
            f'<h2 style="font-size:16px;font-weight:700;padding-bottom:5px;'
            f'border-bottom:1px solid #ddd;margin-bottom:12px">'
            f'{section["icon"]} {section["label"]}</h2>'
            f"{cards}</div>"
        )

    return (
        '<!DOCTYPE html><html><body style="font-family:Georgia,serif;max-width:680px;'
        'margin:0 auto;padding:24px;color:#1a1a1a;background:#fff">'
        f'<h1 style="font-size:22px;font-weight:700;border-bottom:2px solid #222;'
        f'padding-bottom:12px;margin-bottom:20px">🧪 PFAS News Digest — {today}</h1>'
        + "".join(body_parts)
        + '<hr style="border:none;border-top:1px solid #ddd;margin:24px 0">'
        f'<p style="font-size:11px;color:#999;margin:0">'
        f'Generated automatically by PFAS News Digest Agent · {today}</p>'
        '</body></html>'
    )

# ── Send via SendGrid ─────────────────────────────────────────────────────────
def send_email(subject, html_body):
    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type":  "application/json",
        },
        json={
            "personalizations": [{"to": [{"email": TO_EMAIL}]}],
            "from":    {"email": FROM_EMAIL, "name": "PFAS News Digest"},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_body}],
        },
    )
    if resp.status_code == 202:
        print(f"  ✓ Email sent to {TO_EMAIL}")
    else:
        raise RuntimeError(f"SendGrid error {resp.status_code}: {resp.text}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today  = datetime.now().strftime("%A, %B %-d, %Y")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    print(f"PFAS Digest Agent starting — {today}")
    print(f"Topics: {len(TOPICS)}  |  Stories per topic: {MAX_STORIES}")
    print(f"Pause between topics: {PAUSE_BETWEEN_TOPICS}s\n")

    sections = []
    for i, topic in enumerate(TOPICS):
        stories = fetch_stories(client, topic)
        if stories:
            sections.append({**topic, "stories": stories})
        else:
            print(f"  ✗ Skipping '{topic['label']}' — no stories retrieved")

        # Pause between topics to stay within token/min rate limit
        # Skip pause after the last topic
        if i < len(TOPICS) - 1:
            print(f"  ⏸ Pausing {PAUSE_BETWEEN_TOPICS}s before next topic…")
            time.sleep(PAUSE_BETWEEN_TOPICS)

    if not sections:
        raise RuntimeError("No content gathered across any topic — aborting send.")

    print(f"\nDigest complete — {len(sections)}/{len(TOPICS)} topics with content")
    html = build_html(sections, today)
    send_email(f"PFAS News Digest — {today}", html)
    print("Done ✓")

if __name__ == "__main__":
    main()