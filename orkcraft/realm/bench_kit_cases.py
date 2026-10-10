"""🧪 More Test bench cases for External listeners, the Task board and the Calendar, by level (docs/design/test-bench.md
§3.5). Data only; `bench_cases.CASES` takes them after its own.

The levels say what a case asks of the building, as the Agent pool's do (realm/bench_sets.py):

    simple    a few clear items: the building's plain way
    medium    items that take judgement: what is wanted and what only looks like it, a wiki to use, an invitation to read
    parallel  many items at once: a burst of mail, a busy board, a full day of meetings prepared together
"""
from __future__ import annotations


def _msg(sender: str, title: str, body: str, kept: bool, importance: str = "", tags: tuple = ()) -> dict:
    expect: dict = {"kept": kept}
    if importance:
        expect["importance"] = importance
    return {"sender": sender, "title": title, "body": body, "tags": list(tags), "expect": expect}


# -- External listeners -------------------------------------------------------------------------------------------

WATCHTOWER = [
    {
        "id": "customer-orders", "level": "simple",
        "title": "Keep the customers' questions about their orders",
        "expect": "The two customers' questions are kept; the crypto spam and the newsletter are left out.",
        "inputs": {
            "intent": "questions from our customers about their orders: where it is, changes, refunds",
            "messages": [
                _msg("maria.g@gmail.com", "Where is my order #10482?",
                     "I ordered the oak shelf two weeks ago and the tracking hasn't moved since Monday.", True),
                _msg("promo@coin-moon.biz", "Turn $100 into $10,000 this week",
                     "Our AI trading bot guarantees 300% returns. Limited spots!", False),
                _msg("t.okafor@yahoo.com", "Refund for a damaged lamp",
                     "The lamp arrived with a cracked base (order #10511). Can I get a refund or a new one?", True),
                _msg("newsletter@interiors-today.com", "10 shelf styles for autumn",
                     "This week in Interiors Today: shelves, rugs and the colour of the year.", False,
                     tags=("List-Unsubscribe",)),
            ],
        },
    },
    {
        "id": "on-call", "level": "medium",
        "title": "Keep only what means production is down or slow",
        "expect": "The latency alert, the downtime alert and the customer's 'everything times out' are kept, the "
                  "two alerts high; the dependency bump, the billing alert and the conference are left out.",
        "inputs": {
            "intent": "anything that means our production service is down or degraded right now",
            "messages": [
                _msg("alerts@pagerduty.com", "[TRIGGERED] api-prod p99 latency 4.2s > 1s",
                     "Service api-prod: p99 latency 4.2s for 10 minutes. Runbook: https://runbooks/api-latency",
                     True, "high"),
                _msg("noreply@dependabot.com", "Bump requests from 2.31 to 2.32",
                     "Dependabot opened a pull request to update requests.", False, tags=("github",)),
                _msg("alerts@uptime-robot.com", "Monitor is DOWN: checkout.example.com",
                     "checkout.example.com has been down for 3 minutes (HTTP 502).", True, "high"),
                _msg("billing@aws.amazon.com", "Your estimated charges exceeded $500",
                     "Your AWS account's estimated charges for this month are $512.34.", False),
                _msg("ops@acme-retail.com", "Everything times out on your side",
                     "Since 9:40 every call to your API from our stores times out. Is something wrong?", True),
                _msg("events@devconf.io", "Last chance: DevConf early-bird tickets",
                     "Early-bird pricing ends Friday. Talks on observability and SRE.", False,
                     tags=("List-Unsubscribe",)),
            ],
        },
    },
    {
        "id": "sales-leads", "level": "medium",
        "title": "Keep the people who want to buy, not those who sell to us",
        "expect": "The demo request and the prospect's pricing question are kept; the vendor's cold pitch, the "
                  "recruiter and the existing customer's bug are left out, though each mentions buying or the product.",
        "inputs": {
            "intent": "new sales leads: someone outside the company who wants to buy our product or asks for a demo",
            "messages": [
                _msg("cto@brightpath.health", "Demo for a 40-clinic rollout?",
                     "We run 40 clinics and are looking for a booking system before January. Could we see a demo "
                     "next week?", True),
                _msg("sdr@growthrocket.io", "Book more meetings with our outbound platform",
                     "Teams like yours buy our platform to triple their pipeline. 15 minutes this week?", False),
                _msg("anna@pilates-loft.com", "Pricing for 3 studios",
                     "We're comparing tools. What would three studios with 12 instructors cost per month?", True),
                _msg("talent@hirefast.co", "Senior engineers ready to start",
                     "We have five pre-vetted senior engineers. Want their profiles?", False),
                _msg("support@sunrise-yoga.com", "Bookings page shows the wrong timezone",
                     "We're a customer since March; since the update our bookings show in UTC.", False),
            ],
        },
    },
    {
        "id": "key-clients-burst", "level": "parallel",
        "title": "A Monday burst: keep only the three key clients' mail",
        "expect": "The six messages from Northwind, Contoso and Fabrikam are kept, whatever they are about; the "
                  "eight others are left out, including one that only mentions Northwind.",
        "inputs": {
            "intent": "anything written by people at our three key clients: Northwind, Contoso and Fabrikam",
            "messages": [
                _msg("dana.holt@northwind.example", "Renewal paperwork", "Can you send the renewal order form?", True),
                _msg("news@techcrunch.example", "Contoso raises $40M", "Contoso announced a new round today.", False,
                     tags=("List-Unsubscribe",)),
                _msg("li.wei@contoso.example", "SSO is failing for our EU tenant",
                     "Since this morning SSO logins fail for eu.contoso users.", True),
                _msg("noreply@calendly.example", "New meeting booked", "A meeting was booked for Thursday.", False),
                _msg("m.ruiz@fabrikam.example", "Lunch next week?", "We're in town Tuesday, lunch?", True),
                _msg("jobs@linkedin.example", "12 new jobs for you", "Jobs matching your profile.", False,
                     tags=("List-Unsubscribe",)),
                _msg("procurement@northwind.example", "PO 7781 approved", "Purchase order 7781 is approved.", True),
                _msg("sam@ourteam.dev", "Northwind deck v3", "I updated the Northwind deck, have a look.", False),
                _msg("it@contoso.example", "New security questionnaire",
                     "Please fill in our 2026 vendor security questionnaire by the 30th.", True),
                _msg("billing@stripe.example", "Payout sent", "A payout of $8,410 is on its way.", False),
                _msg("ceo@fabrikam.example", "Expanding to two more regions",
                     "We'd like to talk about rolling out to APAC and LATAM next quarter.", True),
                _msg("alerts@statuspage.example", "Scheduled maintenance", "Maintenance on Sunday 02:00 UTC.", False),
                _msg("hello@figma.example", "What's new in Figma", "Dev Mode updates and more.", False,
                     tags=("List-Unsubscribe",)),
                _msg("noreply@github.com", "[app] 3 new issues", "Three issues were opened.", False, tags=("github",)),
            ],
        },
    },
]


# -- Task board ---------------------------------------------------------------------------------------------------

FIELDS = [
    {
        "id": "long-cards", "level": "simple",
        "title": "Name four long cards, one in Russian",
        "expect": "Titles of 2–4 words that say what each card is, the Russian one in Russian.",
        "inputs": {
            "titles": [
                {"text": "Remember to book the venue for Mia's birthday party before the end of the month, the place "
                         "near the park fills up fast in December", "expect_words": [["venue", "party", "birthday"]]},
                {"text": "The laptop battery drains in two hours now, check whether it's still under warranty or "
                         "just order a new battery online", "expect_words": [["laptop", "battery"]]},
                {"text": "Нужно до пятницы отправить бухгалтеру все чеки за сентябрь, иначе не успеем подать "
                         "декларацию вовремя", "expect_words": [["чеки", "чек", "бухгалтер", "декларац"]]},
                {"text": "Write up the notes from Tuesday's design review and send them to Sam and Priya so they "
                         "can start on the onboarding screens", "expect_words": [["notes", "review", "design"]]},
            ],
        },
    },
    {
        "id": "boiler-with-contacts", "level": "medium",
        "title": "Plan a to-do whose text carries an email and a phone",
        "expect": "A plan that uses the wiki (HeatRight, the yearly service the guarantee needs) and brings the "
                  "email back as it was, with no [email-…] or [phone-…] mark left.",
        "files": {
            "README.md": "# Home\n",
            "llm-wiki/general/pages/boiler.md":
                "# Boiler\n\nVaillant ecoTEC plus, fitted 2022. Serviced every October by HeatRight (Tom). The "
                "10-year guarantee holds only with a yearly service and its certificate. Last service: 12 Oct 2025.\n",
        },
        "inputs": {
            "plans": [
                {"title": "Book the boiler service",
                 "body": "Ask Tom (tom@heatright.example, 07700 900123) for a slot before the cold starts.",
                 "expect_words": [["HeatRight", "Tom"], ["tom@heatright.example", "07700 900123"], ["guarantee", "certificate"]]},
            ],
        },
    },
    {
        "id": "russian-passport", "level": "medium",
        "title": "Plan a to-do in Russian with a Russian wiki page",
        "expect": "A plan in Russian that uses the page: Gosuslugi, the photo, the state fee.",
        "files": {
            "README.md": "# Документы\n",
            "llm-wiki/general/pages/passport.md":
                "# Загранпаспорт\n\nСрок действия до 3 марта 2027 года. Подавать через Госуслуги за три месяца до "
                "конца срока. Нужны фотография 35×45 и квитанция об оплате госпошлины 6000 ₽. Старый паспорт "
                "сдают при получении нового.\n",
        },
        "inputs": {
            "plans": [
                {"title": "Продлить загранпаспорт", "body": "Срок скоро заканчивается.",
                 "expect_words": [["Госуслуг"], ["пошлин", "6000"], ["фото"]]},
            ],
        },
    },
    {
        "id": "busy-board", "level": "parallel",
        "title": "A busy board: six cards to name and two to-dos to plan at once",
        "expect": "Every card named in a few words, both plans using the wiki's facts, all of it from one go.",
        "files": {
            "README.md": "# Studio admin\n",
            "llm-wiki/general/pages/studio-lease.md":
                "# Studio lease\n\nLandlord: Brook Properties, contact Helen Marsh. The lease ends on 31 January; "
                "notice to renew must be given in writing 60 days before. Rent £2,150 a month.\n",
            "llm-wiki/general/pages/van.md":
                "# Van\n\nFord Transit, plate KX21 ABC. MOT due 14 November at Lane Garage. Insurance with Drive "
                "Secure, policy DS-55102.\n",
        },
        "inputs": {
            "titles": [
                {"text": "Order more yoga mats and blocks for the Thursday class, we keep running out when more than "
                         "twelve people show up", "expect_words": [["mats", "yoga", "blocks"]]},
                {"text": "Update the website timetable with the new evening classes and remove the Sunday slot that "
                         "nobody comes to anymore", "expect_words": [["timetable", "website", "classes"]]},
                {"text": "Call the plumber about the shower in the changing room, it has been dripping since last "
                         "week and the floor gets slippery", "expect_words": [["shower", "plumber"]]},
                {"text": "Send the October invoices to the three corporate clients and chase the one from August "
                         "that is still unpaid", "expect_words": [["invoices", "invoice"]]},
                {"text": "Find a substitute teacher for the 7am classes while Jo is on holiday from the 3rd to the "
                         "17th", "expect_words": [["substitute", "teacher", "cover"]]},
                {"text": "Renew the first-aid certificates for all instructors, two of them expire before the end of "
                         "the year", "expect_words": [["first-aid", "first", "certificates", "certificate"]]},
            ],
            "plans": [
                {"title": "Renew the studio lease", "body": "Don't miss the notice date.",
                 "expect_words": [["Helen", "Brook"], ["writing", "written", "letter"], ["60", "December"]]},
                {"title": "Get the van ready for winter", "body": "MOT and insurance.",
                 "expect_words": [["Lane Garage", "Lane"], ["14 November", "November"], ["DS-55102", "Drive Secure"]]},
            ],
        },
    },
]


# -- Calendar ------------------------------------------------------------------------------------------------------

_BRIEF = ("Write a short brief for each meeting with the sections ## Agenda, ## People and ## Questions to ask. "
          "Use what the invitation says.")

CALENDAR = [
    {
        "id": "one-to-one", "level": "simple",
        "title": "Brief a 1:1",
        "expect": "One brief that names Alex and carries the two topics from the invitation.",
        "inputs": {
            "orders": _BRIEF, "expect_headings": ["Agenda", "Questions"],
            "events": [
                {"title": "1:1 Alex", "day": 1, "at": "11:00", "minutes": 30, "attendees": ["Alex Kim"],
                 "description": "Topics: Alex's promotion case, and the Q4 goals for the mobile team.",
                 "expect_words": [["Alex"], ["promotion"], ["Q4", "goals"]]},
            ],
        },
    },
    {
        "id": "an-interview", "level": "medium",
        "title": "Brief an interview from the invitation's notes",
        "expect": "A brief that uses the candidate's notes: Jordan, Postgres at scale, the system design focus, and "
                  "the gap to probe.",
        "inputs": {
            "orders": _BRIEF, "expect_headings": ["Agenda", "Questions"],
            "events": [
                {"title": "Interview: senior backend engineer", "day": 1, "at": "15:00", "minutes": 60,
                 "attendees": ["Jordan Lee", "Priya Raman"],
                 "description": "Candidate: Jordan Lee. 8 years backend, last 3 at a payments company running Postgres "
                                "at 20k writes/s. Focus today: system design (a booking system for 1,000 studios). "
                                "Gap to probe: no on-call experience. Priya runs the coding part.",
                 "expect_words": [["Jordan"], ["Postgres"], ["system design", "design"], ["on-call", "on call"]]},
            ],
        },
    },
    {
        "id": "investor-update", "level": "medium",
        "title": "Brief an investor update with its numbers",
        "expect": "A brief that carries the numbers from the invitation (MRR, churn, runway) and the ask.",
        "inputs": {
            "orders": _BRIEF, "expect_headings": ["Agenda", "Questions"],
            "events": [
                {"title": "Investor update: Seedcamp", "day": 1, "at": "10:00", "minutes": 45,
                 "attendees": ["Rachel Stone"],
                 "description": "Numbers to share: MRR $84k (+12% month on month), logo churn 3.1%, runway 14 "
                                "months. The ask: a $500k bridge to hire two engineers before the Series A.",
                 "expect_words": [["84"], ["churn"], ["runway"], ["500", "bridge"]]},
            ],
        },
    },
    {
        "id": "full-day", "level": "parallel",
        "title": "Brief a full day: four meetings prepared at once",
        "expect": "Four briefs, each with its own people and points, none mixed up with another meeting's.",
        "inputs": {
            "orders": _BRIEF, "expect_headings": ["Agenda", "People", "Questions"],
            "events": [
                {"title": "Stand-up", "day": 1, "at": "09:30", "minutes": 15, "attendees": ["Sam Patel", "Mia Chen"],
                 "description": "Blockers only. Sam: the payments migration is waiting on the bank's sandbox.",
                 "expect_words": [["Sam"], ["payments", "migration"], ["sandbox", "bank"]]},
                {"title": "Pricing review", "day": 1, "at": "11:00", "minutes": 60, "attendees": ["Lena Kraus"],
                 "description": "Decide whether the Studio plan goes from $49 to $59. Lena brings the churn data "
                                "from the last increase.",
                 "expect_words": [["Lena"], ["49", "59"], ["churn"]]},
                {"title": "Call with Harbor Yoga", "day": 1, "at": "14:00", "minutes": 30,
                 "attendees": ["Priya Raman"],
                 "description": "They hit a CSV export error last week (fixed Tuesday). They are thinking of adding "
                                "two studios.",
                 "expect_words": [["Priya", "Harbor"], ["CSV", "export"], ["two studios", "studios"]]},
                {"title": "Hiring sync", "day": 1, "at": "16:30", "minutes": 30, "attendees": ["Jo Evans"],
                 "description": "Two offers out (backend, design). Jo wants a decision on the third role: QA or "
                                "a second designer.",
                 "expect_words": [["Jo"], ["offers", "offer"], ["QA", "designer"]]},
            ],
        },
    },
]

CASES: dict[str, list[dict]] = {"watchtower": WATCHTOWER, "fields": FIELDS, "war_drum": CALENDAR}
