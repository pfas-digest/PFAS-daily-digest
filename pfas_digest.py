import os
import json
import anthropic
import requests
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SENDGRID_API_KEY  = os.environ["SENDGRID_API_KEY"]
FROM_EMAIL        = os.environ.get("FROM_EMAIL", "andrew@remotevelocity.com")
TO_EMAIL          = os.environ.get("TO_EMAIL",   "andrew@remotevelocity.com")
MAX_STORIES       = int(os.environ.get("MAX_STORIES", "3"))

TOPICS = [
    {"label": "Regulation & EPA",    "icon": "🏛️", "query": "PFAS regulation EPA policy 2026"},
    {"label": "Water Contamination", "icon": "💧",  "query": "PFAS water contamination drinking water 2026"},
    {"label": "Health Research",     "icon": "🔬",  "query": "PFAS health effects research study 2026"},
    {"label": "Litigation",          "icon": "⚖️",  "query": "PFAS lawsuit litigation settlement 2026"},
    {"label": "Remediation Tech",    "icon": "♻️",  "query": "PFAS cleanup remediation technology 2026"},
    {"label": "Montana news",    "icon": "M",  "query": "PFAS articles news regulations Montana 2026"},
]

# ── Fetch stories for one topic ───────────────────────────────────────────────
def fetch_stories(client, topic):
    print(f"  Searching: {topic['label']}…")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=(
            "You are a news research assistant. Use the web_search tool to find recent, "
            "real news stories. After searching, return ONLY raw JSON — no markdown fences, "
            "no explanation. Format exactly: "
            '{"stories":[{"headline":"...","source":"...","date":"...","url":"...","summary":"2-3 factual sentences"}]}'
        ),
        messages=[{
            "role": "user",
            "content": f"Find the {MAX_STORIES} most recent news stories about: {topic['query']}"
        }],
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
    )

    for block in response.content:
        if block.type == "text":
            try:
                clean = block.text.replace("```json", "").replace("```", "").strip()
                return json.loads(clean).get("stories", [])
            except json.JSONDecodeError:
                pass
    return []

# ── Build HTML email ──────────────────────────────────────────────────────────
def build_html(sections, today):
    story_card = """
    <div style="margin-bottom:12px;padding:12px;background:#f8f8f6;border-left:3px solid #444;border-radius:2px">
      <strong style="font-size:14px;display:block">{headline_link}</strong>
      <span style="font-size:11px;color:#888">{source}{date_part}</span>
      <p style="font-size:13px;color:#444;margin:6px 0 0;line-height:1.55">{summary}</p>
    </div>"""

    body_parts = []
    for section in sections:
        cards = ""
        for s in section["stories"]:
            headline  = s.get("headline", "Untitled")
            url       = s.get("url", "")
            hl_link   = f'<a href="{url}" style="color:#1a1a1a;text-decoration:underline">{headline}</a>' if url else headline
            date_part = f" · {s['date']}" if s.get("date") else ""
            cards += story_card.format(
                headline_link=hl_link,
                source=s.get("source", ""),
                date_part=date_part,
                summary=s.get("summary", ""),
            )
        body_parts.append(f"""
        <div style="margin-bottom:28px">
          <h2 style="font-size:16px;font-weight:700;padding-bottom:5px;
                     border-bottom:1px solid #ddd;margin-bottom:12px">
            {section['icon']} {section['label']}
          </h2>
          {cards}
        </div>""")

    return f"""<!DOCTYPE html>
<html><body style="font-family:Georgia,serif;max-width:680px;margin:0 auto;
                   padding:24px;color:#1a1a1a;background:#fff">
  <h1 style="font-size:22px;font-weight:700;border-bottom:2px solid #222;
             padding-bottom:12px;margin-bottom:20px">
    🧪 PFAS News Digest — {today}
  </h1>
  {"".join(body_parts)}
  <hr style="border:none;border-top:1px solid #ddd;margin:24px 0">
  <p style="font-size:11px;color:#999;margin:0">
    Generated automatically by PFAS News Digest Agent · {today}
  </p>
</body></html>"""

# ── Send via SendGrid ─────────────────────────────────────────────────────────
def send_email(subject, html_body):
    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "personalizations": [{"to": [{"email": TO_EMAIL}]}],
            "from": {"email": FROM_EMAIL, "name": "PFAS News Digest"},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_body}],
        },
    )
    if response.status_code == 202:
        print(f"  ✓ Email sent to {TO_EMAIL}")
    else:
        raise RuntimeError(f"SendGrid error {response.status_code}: {response.text}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today  = datetime.now().strftime("%A, %B %-d, %Y")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    print(f"PFAS Digest Agent starting — {today}")
    print(f"Topics: {len(TOPICS)}  |  Stories per topic: {MAX_STORIES}")

    sections = []
    for topic in TOPICS:
        stories = fetch_stories(client, topic)
        if stories:
            print(f"  ✓ {len(stories)} stories for '{topic['label']}'")
            sections.append({**topic, "stories": stories})
        else:
            print(f"  ⚠ No stories found for '{topic['label']}'")

    if not sections:
        raise RuntimeError("No content gathered — aborting send.")

    html = build_html(sections, today)
    subj = f"PFAS News Digest — {today}"
    send_email(subj, html)
    print("Done ✓")

if __name__ == "__main__":
    main()


