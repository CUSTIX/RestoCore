# Ask RestoCore: the owner's AI assistant

The owner opens **Ask RestoCore** in the sidebar and asks in plain words:

- "How are we doing today?"
- "Compare this week's sales with last week's."
- "What's running low, and what would it cost to restock?"
- "Who is working tomorrow? Is anyone on leave?"
- "What did the last pay period cost us?"

It answers from the live data and lists which parts it looked at, for example
"Looked at: Sales report · Inventory".

## Turn it on (free)

1. Get a free API key at <https://aistudio.google.com/apikey>. You need a Google account; no card.
2. Put it in `.env` (local) or in the Render dashboard (live demo):

   ```
   GEMINI_API_KEY=your-key
   ```

3. Restart (`docker compose up`). Without a key, the page says the assistant is switched off and
   the rest of RestoCore works as before.

Optional settings:

| Variable | Default | Meaning |
|---|---|---|
| `ASSISTANT_MODEL` | `gemini-flash-latest` | Any Gemini model your key may use. Flash models are on the free tier. |
| `ASSISTANT_HOURLY_LIMIT` | `20` | Questions per owner per hour. |
| `ASSISTANT_DAILY_LIMIT` | `200` | Questions for the whole site per day, to protect the free quota on a public demo. |

Google changes its free-tier quotas from time to time; check your current limits in AI Studio. When
the quota runs out, the page says so instead of failing.

## How it works

```
owner question ──► Django view (Owner only, rate-limited)
                     │
                     ▼
               assistant.services.ask ──► Gemini: question + tool list
                     ▲                       │ "call sales_report(2026-11-02..08)"
                     │                       ▼
                     └──── tool result ◄── assistant.tools (read-only selectors)
                     ... repeats (max 6 rounds) until Gemini answers in text
```

- **Tools, not SQL.** The model can call 14 read-only tools: overview, sales report, orders, menu,
  bookings, booking stats, inventory, stock movements, employees, schedule, attendance, leave,
  pay periods and a pay period's payslips. Each tool calls that module's `selectors.py`, the same
  rule every other app follows. It cannot write anything.
- **Facts come from tools.** The system prompt gives today's date and time, opening hours and
  currency, and tells the model to turn "last week" into exact dates, to get every figure from a
  tool, and to say when the data doesn't have the answer.
- **Short memory.** The last 6 questions and answers stay in the owner's session, so follow-ups
  like "and the week before?" work. "New conversation" clears it.
- **No extra dependencies.** `assistant/llm.py` calls the Gemini REST API with the standard library;
  tests swap in a scripted fake model, so CI never calls Google.

## Privacy and safety

- Questions, and the data the tools return to answer them, are sent to Google Gemini. The demo
  holds only fake data. On a free key, Google may use what is sent to improve its products; don't
  use a free key with real customer data.
- Customer phone numbers and emails, and staff phone numbers, are never sent to the model.
- Text written by other people (guest names, booking notes, leave reasons) is marked as data, not
  instructions. Even if someone writes "ignore your instructions" in a booking note, the tools are
  read-only, and answers are rendered as escaped text, never HTML.
- More in [SECURITY.md](../SECURITY.md).
