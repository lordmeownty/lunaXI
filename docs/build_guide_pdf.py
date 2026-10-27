"""Builds docs/Luna_XI_Guide.pdf (Microsoft-style theme). Run: python docs/build_guide_pdf.py"""
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate, PageBreak, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

FONT_DIR = Path("/usr/share/fonts/dejavu-sans-fonts")
pdfmetrics.registerFont(TTFont("UI", str(FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("UI-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("UI-Light", str(FONT_DIR / "DejaVuSans-ExtraLight.ttf")))
pdfmetrics.registerFontFamily("UI", normal="UI", bold="UI-Bold", italic="UI", boldItalic="UI-Bold")

BLUE = colors.HexColor("#0F6CBD"); BLUE_L = colors.HexColor("#EBF3FC"); BLUE_M = colors.HexColor("#479EF5")
INK = colors.HexColor("#242424"); GREY = colors.HexColor("#616161"); LINE = colors.HexColor("#E0E0E0"); SOFT = colors.HexColor("#F5F5F5")
MS = [colors.HexColor("#F25022"), colors.HexColor("#7FBA00"), colors.HexColor("#00A4EF"), colors.HexColor("#FFB900")]
W, H = A4
M = 20 * mm

S = {
    "h1": ParagraphStyle("h1", fontName="UI-Bold", fontSize=20, leading=25, textColor=INK, spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="UI-Bold", fontSize=13, leading=17, textColor=BLUE, spaceBefore=12, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="UI-Bold", fontSize=10.5, leading=14, textColor=INK, spaceBefore=8, spaceAfter=3),
    "body": ParagraphStyle("body", fontName="UI", fontSize=9.5, leading=14.2, textColor=INK, spaceAfter=6, alignment=TA_LEFT),
    "small": ParagraphStyle("small", fontName="UI", fontSize=8.3, leading=11.5, textColor=GREY),
    "cell": ParagraphStyle("cell", fontName="UI", fontSize=8.3, leading=10.9, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="UI-Bold", fontSize=8.3, leading=10.9, textColor=INK),
    "head": ParagraphStyle("head", fontName="UI-Bold", fontSize=8.4, leading=11.4, textColor=colors.white),
    "bullet": ParagraphStyle("bullet", fontName="UI", fontSize=9.5, leading=14, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "callout": ParagraphStyle("callout", fontName="UI", fontSize=9.5, leading=14, textColor=INK),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8.2, leading=11, textColor=INK),
}


def P(t, s="body"): return Paragraph(t, S[s])
def B(items): return [Paragraph(i, S["bullet"], bulletText="•") for i in items]


def table(rows, widths, head=True, zebra=True):
    data = [[P(c, "head" if (head and r == 0) else ("cellb" if c0 == 0 and len(rows[0]) > 2 else "cell")) if isinstance(c, str) else c
             for c0, c in enumerate(row)] for r, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE)]
    if head:
        st += [("BACKGROUND", (0, 0), (-1, 0), BLUE)]
    if zebra:
        st += [("BACKGROUND", (0, i), (-1, i), SOFT) for i in range(2 if head else 1, len(rows), 2)]
    t.setStyle(TableStyle(st))
    return t


def callout(text, title=None):
    inner = [P(f"<b>{title}</b>", "callout")] if title else []
    inner.append(P(text, "callout"))
    t = Table([[inner]], colWidths=[W - 2 * M])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE_L), ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    return t


def box(d, x, y, w, h, title, sub="", fill=colors.white, stroke=BLUE, tcol=INK):
    d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=0.9))
    d.add(String(x + w / 2, y + h - 13, title, fontName="UI-Bold", fontSize=8, fillColor=tcol, textAnchor="middle"))
    if sub:
        for i, line in enumerate(sub.split("\n")):
            d.add(String(x + w / 2, y + h - 24 - i * 9, line, fontName="UI", fontSize=6.5, fillColor=GREY, textAnchor="middle"))


def arrow(d, x1, y1, x2, y2, col=GREY):
    d.add(Line(x1, y1, x2, y2, strokeColor=col, strokeWidth=0.9))
    import math
    a = math.atan2(y2 - y1, x2 - x1); s = 4
    d.add(Polygon([x2, y2, x2 - s * math.cos(a - .45), y2 - s * math.sin(a - .45), x2 - s * math.cos(a + .45), y2 - s * math.sin(a + .45)],
                  fillColor=col, strokeColor=col))


def architecture():
    d = Drawing(W - 2 * M, 250)
    cw = W - 2 * M
    box(d, 0, 200, cw, 40, "Browser · React + Three.js (Microsoft Fluent-style UI)",
        "Sign in with Microsoft · Home · Match workspace · Recaps · Studio · Approvals · Operations · Luna voice drawer", fill=BLUE_L)
    box(d, 0, 105, cw * .62, 78, "Luna XI API · FastAPI (Azure Container Apps)",
        "Security: sign-in · roles · rate limits · Prompt Shields · audit\nAgent workflow (Microsoft Agent Framework): 11 agents\nDeterministic analytics · Evidence Referee · Key Vault secrets")
    box(d, cw * .65, 105, cw * .35, 78, "Microsoft Foundry", "GPT Realtime · GPT Transcribe\nJev / Microsoft-Decision-1\nGPT-6 Luna · Sol (reasoning)\nImage model", fill=colors.HexColor("#F3F0FF"), stroke=colors.HexColor("#6B4FBB"))
    box(d, 0, 10, cw * .3, 78, "Synthetic data", "5 fictional matches\nOpen Football (build-time)\nreplay keyframes + ground truth", fill=colors.HexColor("#EEF7EE"), stroke=colors.HexColor("#2E7D32"))
    box(d, cw * .33, 10, cw * .67, 78, "Azure services (hosting phase)",
        "Key Vault · Container Apps · Static Web Apps · Event Hubs → Functions → Cosmos DB\nService Bus → Functions → Blob + Logic App → Teams · App Insights",
        fill=colors.HexColor("#FFF8E6"), stroke=colors.HexColor("#B7791F"))
    arrow(d, cw * .3, 200, cw * .3, 184, BLUE); d.add(String(cw * .3 + 4, 190, "REST · SSE (ticket)", fontName="UI", fontSize=6.5, fillColor=GREY))
    arrow(d, cw * .82, 200, cw * .82, 184, colors.HexColor("#6B4FBB")); d.add(String(cw * .82 + 4, 190, "WebRTC voice", fontName="UI", fontSize=6.5, fillColor=GREY))
    arrow(d, cw * .62, 145, cw * .65, 145, colors.HexColor("#6B4FBB"))
    arrow(d, cw * .15, 105, cw * .15, 89, colors.HexColor("#2E7D32"))
    arrow(d, cw * .5, 105, cw * .5, 89, colors.HexColor("#B7791F"))
    return d


def workflow():
    d = Drawing(W - 2 * M, 170)
    pos = {"safety": (0, 70), "observe": (88, 70), "route": (176, 70), "lookup": (290, 140), "judge": (290, 98), "summarise": (400, 120),
           "explain": (400, 62), "replay": (290, 40), "package": (290, 0)}
    sub = {"safety": "Prompt Shields", "observe": "clock · focus", "route": "Decision model", "lookup": "T0 data", "judge": "T1 judgement",
           "summarise": "T2 Luna+Referee", "explain": "T3 Sol+Referee", "replay": "R Luna Lens", "package": "T4 recap"}
    for k, (x, y) in pos.items():
        box(d, x, y, 80, 30, k, sub[k], fill=BLUE_L if k in ("safety", "observe", "route") else colors.white)
    edges = [("safety", "observe"), ("observe", "route"), ("route", "lookup"), ("route", "judge"), ("route", "summarise"), ("route", "explain"),
             ("route", "replay"), ("route", "package"), ("lookup", "summarise"), ("judge", "explain"), ("judge", "summarise")]
    for a, b in edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        arrow(d, x1 + 80, y1 + 15, x2, y2 + 15, BLUE_M)
    return d


def on_page(c, doc):
    c.saveState()
    c.setFillColor(BLUE); c.rect(0, H - 6, W, 6, fill=1, stroke=0)
    for i, col in enumerate(MS):
        c.setFillColor(col); c.rect(M + (i % 2) * 5.2, H - 16 - (i // 2) * 5.2, 4.6, 4.6, fill=1, stroke=0)
    c.setFont("UI-Bold", 8); c.setFillColor(INK); c.drawString(M + 15, H - 14.5, "Luna XI")
    c.setFont("UI", 8); c.setFillColor(GREY); c.drawString(M + 52, H - 14.5, "Complete guide · Inside the Game hackathon")
    c.drawRightString(W - M, 12 * mm, f"{doc.page}")
    c.drawString(M, 12 * mm, "All teams, players and matches are fictional.")
    c.setStrokeColor(LINE); c.line(M, 15 * mm, W - M, 15 * mm)
    c.restoreState()


def on_cover(c, doc):
    c.saveState()
    c.setFillColor(colors.HexColor("#0B1B2E")); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(BLUE); c.circle(W * 0.92, H * 0.82, 210, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#0B1B2E")); c.circle(W * 0.83, H * 0.86, 190, fill=1, stroke=0)
    for i, col in enumerate(MS):
        c.setFillColor(col); c.rect(M + (i % 2) * 13, H - 40 * mm - (i // 2) * 13, 11.5, 11.5, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("UI-Bold", 46); c.drawString(M, H * 0.52, "Luna XI")
    c.setFont("UI-Light", 22); c.drawString(M, H * 0.52 - 34, "Football, understood.")
    c.setFillColor(colors.HexColor("#9CC8FA")); c.setFont("UI", 11.5)
    c.drawString(M, H * 0.52 - 70, "Explainable match intelligence, live narratives, automated recaps and")
    c.drawString(M, H * 0.52 - 86, "personalised experiences on Microsoft Foundry and Azure.")
    c.setFillColor(colors.white); c.setFont("UI-Bold", 10); c.drawString(M, 46 * mm, "Complete guide")
    c.setFont("UI", 9.5); c.setFillColor(colors.HexColor("#C8D3E0"))
    for i, t in enumerate(["What it is and who it is for · How everything connects · Voice · Foundry models",
                           "Multi-agent workflow · Security and roles · Prize-category mapping · Demo script · Setup"]):
        c.drawString(M, 40 * mm - i * 13, t)
    c.setFont("UI", 8); c.drawString(M, 18 * mm, "Inside the Game: Developer Hackathon · Version 1.2 · All data synthetic and fictional")
    c.restoreState()


def build(out: Path):
    doc = BaseDocTemplate(str(out), pagesize=A4, leftMargin=M, rightMargin=M, topMargin=24 * mm, bottomMargin=20 * mm,
                          title="Luna XI: Complete guide", author="Luna XI team")
    frame = Frame(M, 20 * mm, W - 2 * M, H - 44 * mm, id="f")
    doc.addPageTemplates([PageTemplate("cover", [Frame(0, 0, W, H)], onPage=on_cover), PageTemplate("page", [frame], onPage=on_page)])
    cw = W - 2 * M
    s = [NextPageTemplate("page"), PageBreak()]

    # 1 ------------------------------------------------------------------------------------------------
    s += [P("1. Luna XI in one page", "h1"),
          callout("Luna XI turns synthetic football events into stories people can <b>talk to</b>, <b>see</b> and <b>trust</b>. Fans ask by voice and "
                  "watch any goal rebuilt in 3D. Analysts get evidence-backed explanations. Broadcasters check commentary before it airs and send "
                  "recap packages for editorial approval. Operators can see what every model and agent did and what it cost.", "The one-sentence pitch"),
          Spacer(1, 8), P("Who it is for and why it matters", "h2"),
          table([["Who", "Problem today", "What Luna XI does", "Value"],
                 ["Fan / streaming viewer", "Joins late, misses the story, stats don't explain why", "Voice companion, catch-me-up, explanations at their level, audio-first mode, 3D replays", "Longer sessions, return visits, accessibility"],
                 ["Analyst", "Hours digging through event data", "\"Why did momentum change?\" with before/after numbers and visual proof", "Faster insight"],
                 ["Broadcaster", "Wrong claims on air; slow packages", "Commentary transcribed and every claim checked against events; verified recap packages", "Fewer on-air corrections"],
                 ["Editor", "No control over AI-assisted content", "Approval queue, separation of duties, audited decisions", "Nothing airs unreviewed"],
                 ["Operator", "AI cost and risk are invisible", "Agent workflow view, cost saved, safety, Key Vault, audit log", "Governed, predictable AI"]],
                [cw * .17, cw * .25, cw * .38, cw * .20]),
          P("How it covers the brief", "h2"),
          table([["The brief asks for…", "Where it lives in Luna XI"],
                 ["Explainable match intelligence", "Every answer shows its evidence, a \"Verified\" badge from the Evidence Referee, and the full agent trace; Luna Lens shows the proof in 3D."],
                 ["Real-time narratives", "Live simulation streams events; the story feed, match pulse and moment rail update as the match unfolds."],
                 ["Automated recaps", "Recap Studio builds half-time, full-time or so-far recaps for five audiences, plus talking points and a replay reel."],
                 ["Personalised experiences", "Fan, New fan, Tactical, Broadcaster and Audio-first modes; voice; role-specific screens."],
                 ["Fans, studios, broadcasters, streaming", "Each has its own role and screens; the Director can see them all."]],
                [cw * .32, cw * .68])]

    # 2 ------------------------------------------------------------------------------------------------
    s += [PageBreak(), P("2. How everything connects", "h1"),
          P("Every screen reads the <b>same verified event data</b>. That is the core design decision: the fan's answer, the analyst's explanation, the 3D replay "
            "and the broadcaster's package can never contradict each other, because they all come from one source and every number is checked."),
          architecture(), Spacer(1, 6), P("The thread through the product", "h2"),
          table([["Step", "What happens", "Connected to"],
                 ["1 · Sign in", "\"Sign in with Microsoft\" signs you in as the Director (demo). Your role decides what you can open.", "Audit log, role permissions"],
                 ["2 · Home", "Choose one of five fictional matches (unchanged design).", "Match workspace"],
                 ["3 · Match workspace", "The moment rail is the spine: pick a moment and the 3D replay, focus card, pulse marker, story and Luna all follow it.", "Luna, Luna Lens, stats"],
                 ["4 · Luna (voice or text)", "Ask questions or give commands. The decision model routes each request to the cheapest reliable path; the Referee checks the answer.", "Foundry models, agents, replay"],
                 ["5 · Recaps", "Generate a recap for any audience; broadcasters submit it for approval.", "Approvals, Service Bus"],
                 ["6 · Studio", "Load or upload commentary; claims are checked against the events; \"Show proof\" opens the replay.", "GPT Transcribe, Luna Lens"],
                 ["7 · Approvals", "Editors approve or request changes (never their own package). The bell shows how many are waiting.", "Audit log, Functions, Teams"],
                 ["8 · Operations", "Agent workflow graph, models, cost saved, Key Vault and security status, audit log.", "Everything above"]],
                [cw * .2, cw * .55, cw * .25]),
          Spacer(1, 6),
          callout("Breadcrumbs (Home › Match › Section), a match switcher, deep links (#/match/&lt;id&gt;/studio) and the rail on the left mean every "
                  "screen is one click from every other. You never need to go back to Home to reach Recaps, Studio, Approvals or Operations.", "Navigation")]

    # 3 ------------------------------------------------------------------------------------------------
    s += [PageBreak(), P("3. The match workspace, piece by piece", "h1"),
          table([["Area", "What it shows", "How to use it"],
                 ["Top bar", "Breadcrumbs with a match switcher, live scoreboard and clock, approvals bell, your account (View as).", "Switch match without leaving the section you're in."],
                 ["Mode bar", "Full match (whole story) or Live simulation (stream with play, pause, restart and speed 60/240/600×).", "Space bar plays and pauses in live mode."],
                 ["Moment rail", "Two lanes (home and away) over a 0–95' ruler. Goals show the score after the goal; cards, substitutions, tactical changes, big chances and momentum shifts each have an icon.", "Click a marker, or use ← → when the rail is focused, or the arrows at the top right."],
                 ["Luna Lens (3D)", "The selected goal rebuilt from synthetic keyframes: numbered passes, the shot curve and the target zone in the goal.", "Camera: Broadcast, Tactical, Shooter, Keeper. Scrub, pause, restart."],
                 ["Goal reel", "Every goal as a chip in team colours. Locked until reached in live mode (no spoilers).", "Click to replay."],
                 ["Focus card", "The selected moment: type, minute, team, player, score, passes, build-up time, xG.", "Watch in 3D · Explain · Catch me up · step to the previous or next moment."],
                 ["Match pulse", "Momentum (threat index per 5 minutes) with a blue marker at the focused minute, plus team stat bars.", "Read who was on top and when."],
                 ["Match story", "Narrative feed of key moments, chances and saves.", "Click any item to focus it."],
                 ["Luna drawer", "Conversation, evidence chips, Verified badge, tier, \"How it worked\" agent trace, suggestions that change with the focused moment.", "Type, press the mic, or press V."]],
                [cw * .16, cw * .5, cw * .34]),
          P("Roles and the Director", "h2"),
          table([["Role", "Can do", "Sees"],
                 ["Director", "Everything below, plus \"View as\" any role", "Match, Recaps, Studio, Approvals, Operations"],
                 ["Fan", "Watch, ask, voice, recaps (verified summaries, not deep reasoning)", "Match, Recaps"],
                 ["Analyst", "+ deep tactical analysis (reasoning model)", "Match, Recaps"],
                 ["Broadcaster", "+ Broadcast Studio, submit packages", "+ Studio, Approvals (own submissions)"],
                 ["Editor", "+ approve or reject packages (never their own)", "+ Approvals"],
                 ["Admin", "+ operations, audit, event publishing", "+ Operations"]],
                [cw * .16, cw * .5, cw * .34]),
          Spacer(1, 6),
          callout("Open your avatar menu and pick a role under <b>View as</b>. A yellow banner shows you are previewing; buttons and screens follow that role "
                  "exactly, and every switch is written to the audit log. A seeded package from the Broadcaster is waiting, so you can demo approval straight "
                  "away. If you submit your own package, Luna blocks you from approving it (separation of duties).", "Director tip")]

    # 4 ------------------------------------------------------------------------------------------------
    s += [PageBreak(), P("4. Voice: talk to the match", "h1"),
          P("Press the microphone in the Luna drawer, the floating <b>Talk to Luna</b> button on the replay, or the <b>V</b> key. Luna listens continuously "
            "until you press stop. Status shows Listening (red), Thinking (purple) or Speaking (green)."),
          table([["Mode", "When", "How it works"],
                 ["GPT Realtime (primary)", "Foundry keys are set", "The API mints a short-lived secret; the browser connects to Foundry over WebRTC. Luna hears you, calls tools "
                  "(ask_match, show_replay, control_app) and answers aloud. Server-side voice activity detection handles turn-taking."],
                 ["Browser speech (fallback)", "No keys, or WebRTC blocked", "Edge or Chrome speech recognition turns speech into text; commands run instantly, questions go to Luna, and the "
                  "reply is spoken back. Switches automatically, so voice works even offline."]],
                [cw * .2, cw * .2, cw * .6]),
          P("What you can say", "h2"),
          table([["Say", "What happens"],
                 ["\"Show me the last goal from the keeper's view\"", "Replay opens in the goalkeeper camera; Luna describes the move."],
                 ["\"Show me goal three\" / \"the sixth goal\"", "Opens that goal (blocked if it hasn't happened yet in live mode)."],
                 ["\"Why did momentum change?\" / \"Why did this happen?\"", "Tactical explanation with before/after evidence, verified."],
                 ["\"Catch me up\" / \"What happened in the last 10 minutes?\"", "Verified summary."],
                 ["\"Who scored the second goal?\" / \"What's the score?\"", "Instant answer straight from the data (no model call)."],
                 ["\"Play\" · \"Pause\" · \"Restart\"", "Controls the live simulation."],
                 ["\"Next moment\" · \"Previous\"", "Steps the moment rail; the replay and stats follow."],
                 ["\"Keeper view\" · \"Tactical view\" · \"Shooter view\"", "Changes the Luna Lens camera."],
                 ["\"Open studio\" · \"Go to approvals\" · \"Open operations\"", "Navigates (only if your role allows)."],
                 ["\"Open the comeback match\"", "Switches match."],
                 ["\"Speed 600\" · \"Explain it simply\"", "Changes playback speed or explanation style."]],
                [cw * .45, cw * .55]),
          Spacer(1, 6),
          callout("1) Use Edge or Chrome on localhost or HTTPS (browsers only allow the microphone there). 2) Allow microphone access when asked. "
                  "3) With Foundry keys, confirm the realtime deployment name in .env; if your region uses different URLs, set "
                  "FOUNDRY_REALTIME_CLIENT_SECRET_URL and FOUNDRY_REALTIME_WEBRTC_URL. 4) If anything fails, Luna falls back to browser speech and says so in the chat.",
                  "Making voice work reliably")]

    # 5 ------------------------------------------------------------------------------------------------
    s += [PageBreak(), P("5. Microsoft Foundry: how the models are used", "h1"),
          P("Six Foundry models each have <b>one job</b>. Numbers are never invented by a model: deterministic analytics compute every statistic, "
            "and models only explain and narrate verified facts."),
          table([["Model", "Job in Luna XI", "Where you see it"],
                 ["GPT Realtime", "Live speech-to-speech conversation; calls tools to answer and drive the app", "Luna voice"],
                 ["GPT Transcribe", "Commentary or producer audio → text", "Broadcast Studio upload"],
                 ["Jev / Microsoft-Decision-1", "Typed decisions: routes each request, judges shot danger, scores grounding for the Referee", "\"How it worked\" (Decision Router)"],
                 ["GPT-6 Luna (fast)", "Narratives, catch-ups, recaps, claim extraction", "Most answers and recaps"],
                 ["Sol (reasoning)", "Tactical \"why\" explanations with before/after evidence", "Analyst+ questions"],
                 ["Image model", "Recap poster art, labelled \"illustrative, not evidence\"", "Recap Studio"]],
                [cw * .24, cw * .5, cw * .26]),
          P("The AI Efficiency Gateway (cost and quality)", "h2"),
          table([["Tier", "Example", "Handled by", "Cost"],
                 ["T0 lookup", "Who scored the second goal?", "Data Analyst (no model)", "Free"],
                 ["T1 judgement", "Was that shot dangerous?", "Decision model + template", "Tiny"],
                 ["T2 summary", "Catch me up", "GPT-6 Luna + Referee", "Low"],
                 ["T3 reasoning", "Why did the substitution change the match?", "Sol + Referee (+ retry)", "Higher"],
                 ["R replay", "Show goal six from the keeper's view", "Replay Builder + Director", "Free / low"],
                 ["T4 package", "Give me the broadcaster package", "Studio Producer workflow", "Low"]],
                [cw * .16, cw * .38, cw * .3, cw * .16]),
          P("Confidence gate: 85% or more means follow the route; 60–85% moves up one tier; below 60% escalates to reasoning. Fans get verified summaries "
            "instead of the reasoning model. A daily budget guard switches to deterministic answers if the limit is reached. Operations shows "
            "measured cost and reasoning calls avoided."),
          callout("Luna XI uses Foundry as the model platform: one endpoint, six deployments with distinct roles, decision-model routing for cost, realtime "
                  "voice with tool calling, and a 22-case evaluation set (routing, ground truth, replays, spoilers, role limits, safety, referee) that can be "
                  "uploaded as a Foundry evaluation dataset.", "Pitch line for the Foundry category")]

    # 6 ------------------------------------------------------------------------------------------------
    s += [PageBreak(), P("6. Multi-agent orchestration", "h1"),
          P("Every question runs through one workflow graph. Each step is an <b>executor</b>; all of them read and write a single shared state "
            "(the blackboard). With <b>Microsoft Agent Framework</b> installed, the graph runs on its WorkflowBuilder; otherwise the same steps run on a "
            "built-in engine. Behaviour is identical, and the active engine is shown in Operations and in every trace."),
          workflow(), Spacer(1, 4),
          table([["#", "Agent", "Responsibility", "Powered by"],
                 ["1", "Match Observer", "Match state at the playback clock; applies the moment you selected", "deterministic"],
                 ["2", "Data Analyst", "Verified stats; instant answers", "deterministic"],
                 ["3", "Moment Scout", "Momentum shifts and turning points", "deterministic"],
                 ["4", "Decision Router", "Picks the tier (AI Efficiency Gateway)", "Jev / Decision-1"],
                 ["5", "Tactical Analyst", "Explains why with before/after evidence", "Sol"],
                 ["6", "Replay Builder", "Loads and validates keyframes (spoiler-safe)", "deterministic"],
                 ["7", "Replay Director", "Camera and overlays", "deterministic"],
                 ["8", "Evidence Referee", "Rejects unsupported numbers; triggers a retry", "rules + decision model"],
                 ["9", "Story Director", "Audience-specific narratives", "GPT-6 Luna"],
                 ["10", "Voice Director", "Realtime voice and transcription", "GPT Realtime, GPT Transcribe"],
                 ["11", "Studio Producer", "Recap packages, posters, commentary checks", "Luna + image model"]],
                [cw * .06, cw * .2, cw * .5, cw * .24]),
          P("Failure recovery (what judges look for)", "h2")] + B([
          "<b>Referee rejection:</b> a draft with an unsupported number is rejected; the agent retries with the Referee's feedback; if it fails again, a verified deterministic template is used.",
          "<b>Model outage or budget reached:</b> every model step falls back to deterministic analytics, so answers keep flowing.",
          "<b>Engine fallback:</b> if Agent Framework is missing or errors, the run continues on the built-in engine and the trace records it.",
          "<b>Spoiler protection and safety blocks</b> appear as explicit steps in the trace.",
          "<b>A2A:</b> /.well-known/agent.json and JSON-RPC message/send let another organisation's agent delegate questions to Luna XI."])

    # 7 ------------------------------------------------------------------------------------------------
    s += [PageBreak(), P("7. Enterprise: sign-in, roles, audit and Key Vault", "h1"),
          table([["Control", "What is in place"],
                 ["Sign in with Microsoft", "Microsoft-branded sign-in. In the demo it is simulated and signs you in as Director. The production path (MSAL with "
                  "PKCE plus server-side Entra token validation) is already in the code and tested, and is switched on by configuration."],
                 ["Role-based access", "Six roles (Director, Fan, Analyst, Broadcaster, Editor, Admin) mapped to capabilities in one matrix. The UI hides what you "
                  "can't use, and the API enforces it on every request."],
                 ["Director + View as", "One role sees everything; \"View as\" previews any role. A Fan cannot escalate with the preview header. Every switch is audited."],
                 ["Separation of duties", "Nobody can approve a package they submitted, including the Director."],
                 ["Audit log", "Append-only and hash-chained (each record stores the previous record's hash). Persisted to disk and checked live in Operations. "
                  "Records sign-ins, role previews, blocked prompts, approvals, voice sessions and event publishing."],
                 ["Azure Key Vault", "The Foundry key and the stream-ticket secret live in Key Vault (RBAC, soft delete, purge protection). The API reads them with its "
                  "managed identity; Operations shows where each secret came from."],
                 ["Prompt protection", "Azure AI Content Safety Prompt Shields when configured, plus local injection rules; models treat user text as data."],
                 ["Other", "Per-user rate limits, security headers, CSP, 2-minute tickets for the live feed, ephemeral voice secrets, daily AI budget guard."]],
                [cw * .24, cw * .76]),
          P("8. Data and Open Football", "h1")] + B([
          "Five fictional matches: The Comeback, The Tactical Battle, The Goal Festival, The Underdog, The Controversial Finish. Each has its own story.",
          "Every package carries provenance: synthetic = true, contains_real_match_data = false, plus the generator seed.",
          "Open Football (Apache-2.0) is integrated at build time only: pinned revision, fictional database export, and a converter that rebuilds coordinates and replays. "
          "It is never called at runtime and its real-world database is never used."]) + [
          P("9. Azure (hosting phase, later)", "h1"),
          P("Ready in infra/main.bicep and infra/deploy.sh: Container Apps (API), Static Web Apps (web), Key Vault, Event Hubs → Functions → Cosmos DB, "
            "Service Bus → Functions → Blob and Logic App → Teams, App Insights, ACR, all using managed identity. Not deployed yet; validate with "
            "<font face='Courier'>az bicep build</font> before deploying.")]

    # 10 -----------------------------------------------------------------------------------------------
    s += [PageBreak(), P("10. Prize categories: what to say and what to show", "h1"),
          table([["Category", "Say", "Show"],
                 ["Grand Prize", "One connected product covering every part of the brief for every audience, with verified answers.", "Moment rail driving the replay, Luna and stats; voice; Studio; approval."],
                 ["Best Use of Foundry", "Six Foundry models with distinct jobs, decision-model routing for cost, realtime voice with tools, evaluation set.", "Operations: models, tiers, reasoning calls avoided; a T0 vs T3 answer."],
                 ["Best Multi-Agent", "Eleven agents on a Microsoft Agent Framework workflow, shared state, Referee retries, fallbacks, A2A.", "Agent workflow graph lighting up; \"How it worked\" trace with a retry."],
                 ["Best Enterprise", "Microsoft sign-in, roles, Director preview, separation of duties, hash-chained audit, Key Vault, Prompt Shields.", "Sign-in, View as Fan, blocked self-approval, audit log, Key Vault panel."],
                 ["Best Azure Cloud-Native", "Event-driven Azure design, ready to deploy (hosting phase).", "Architecture slide; Bicep."]],
                [cw * .2, cw * .45, cw * .35]),
          P("11. Two-minute demo script", "h1"),
          table([["Time", "Do", "Say"],
                 ["0:00", "Click Sign in with Microsoft", "\"Secured with Microsoft sign-in; your role decides what you see.\""],
                 ["0:10", "Home → The Goal Festival", "\"Five fictional matches, every event synthetic.\""],
                 ["0:18", "Live simulation → Kick off (240×)", "Rail fills, pulse moves, story builds."],
                 ["0:28", "Press V: \"Show me the last goal from the keeper's view\"", "Luna Lens plays; Luna speaks."],
                 ["0:45", "Say \"next moment\", then \"why did this happen?\"", "Focus, pulse marker and Luna follow; Verified + evidence."],
                 ["1:00", "Operations → agent workflow", "\"Eleven agents on Microsoft Agent Framework; routing saved reasoning calls.\""],
                 ["1:12", "The Controversial Finish → Studio → verify", "\"Solo run\" flagged misleading → Show proof in 3D."],
                 ["1:28", "Approvals → approve the seeded package; try your own", "Separation of duties blocks self-approval."],
                 ["1:42", "Avatar → View as Fan", "Studio and Operations disappear; audit records the switch."],
                 ["1:52", "Operations → Key Vault + audit chain", "\"Secrets in Key Vault; every action audited.\""]],
                [cw * .09, cw * .43, cw * .48])]

    # 12 -----------------------------------------------------------------------------------------------
    s += [PageBreak(), P("12. Setup and running", "h1"),
          table([["Step", "Command / action"],
                 ["1. Prerequisites", "Python 3.11+, Node 20+, Edge or Chrome."],
                 ["2. Configure", "cp .env.example .env (works offline). Add FOUNDRY_ENDPOINT, FOUNDRY_API_KEY and your exact deployment names for live AI and voice."],
                 ["3. Install", "make setup   (Python + npm packages)"],
                 ["4. Agent Framework (optional)", "make agents   (pip install --pre agent-framework). Without it the built-in engine runs the same graph."],
                 ["5. Run API", "make api   → http://localhost:8000/docs"],
                 ["6. Run web", "make web   → http://localhost:5173"],
                 ["7. Sign in", "Click Sign in with Microsoft (Director). Use View as in the avatar menu to preview other roles."],
                 ["8. Test", "make test (API, roles, preview, approvals, safety, tickets, A2A, Entra tokens) · make eval (22 cases)"],
                 ["Docker (alternative)", "docker compose up --build → http://localhost:8080"]],
                [cw * .26, cw * .74]),
          P("Troubleshooting", "h2"),
          table([["Symptom", "Fix"],
                 ["Voice says \"browser speech\"", "Foundry Realtime isn't configured or reachable. Check keys and FOUNDRY_REALTIME_DEPLOYMENT; set the realtime URLs if your region differs."],
                 ["Microphone does nothing", "Use Edge or Chrome on localhost, allow the microphone, and check the OS input device."],
                 ["Answers say \"deterministic\" in the trace", "Expected without keys. Add Foundry keys to use the models."],
                 ["Operations shows engine = builtin", "Install Agent Framework (make agents) and keep ORCHESTRATOR=agent_framework."],
                 ["Can't approve a package", "You submitted it yourself. Approve the seeded package, or have another role approve yours."],
                 ["Studio or Operations greyed out", "You are previewing a role without access. Exit preview from the yellow banner."]],
                [cw * .3, cw * .7]),
          P("What was tested and what still needs your machine", "h2")] + B([
          "<b>Tested here:</b> backend tests (including real RS256 Entra tokens), 22/22 evaluation cases on both engines (built-in, and the Agent Framework adapter against a stand-in of its API), TypeScript type-check, and the voice command parser.",
          "<b>Needs your machine:</b> npm install and npm run build; the real agent-framework package (its preview API may differ slightly; Luna falls back automatically); a live GPT Realtime session with your keys; az bicep build before hosting."])

    doc.build(s)


if __name__ == "__main__":
    out = Path(__file__).with_name("Luna_XI_Guide.pdf")
    build(out)
    print(out)
