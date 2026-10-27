"""Luna XI Azure Functions (Python v2): event-driven backbone (identity-based connections).
1. moment_detector          Event Hubs → key moments → Cosmos DB + Service Bus queue
2. publish_approved_package Service Bus topic (publisher) → approved packages → Blob (published/)
3. notify_editorial         Service Bus topic (notify) → Logic App → Teams Adaptive Card
4. nightly_quality_gate     Timer → evaluation probe against the API"""
import json
import logging
import os
import urllib.request

import azure.functions as func

app = func.FunctionApp()
MOMENT_TYPES = {"goal", "card", "substitution", "tactical_change", "save"}


@app.event_hub_message_trigger(arg_name="events", event_hub_name="%EVENTHUB_NAME%", connection="EventHub", cardinality="many", consumer_group="moment-detector")
@app.cosmos_db_output(arg_name="moments", database_name="luna", container_name="moments", connection="Cosmos", create_if_not_exists=False)
@app.service_bus_queue_output(arg_name="alerts", queue_name="moments-queue", connection="ServiceBus")
def moment_detector(events: list[func.EventHubEvent], moments: func.Out[func.DocumentList], alerts: func.Out[str]):
    found = []
    for ev in events:
        e = json.loads(ev.get_body().decode())
        if e.get("type") in MOMENT_TYPES or (e.get("type") == "shot" and (e.get("xg") or 0) >= 0.3):
            found.append(func.Document.from_dict({"id": f"{e['match_id']}-{e['id']}", "matchId": e["match_id"], "eventId": e["id"], "type": e["type"],
                                                  "clock": e.get("clock"), "team": e.get("team"), "player": e.get("player"), "xg": e.get("xg")}))
    if found:
        moments.set(func.DocumentList(found))
        alerts.set(json.dumps({"count": len(found), "matchId": found[0]["matchId"]}))
    logging.info("moment_detector: %d events -> %d moments", len(events), len(found))


@app.service_bus_topic_trigger(arg_name="msg", topic_name="%SERVICEBUS_TOPIC%", subscription_name="publisher", connection="ServiceBus")
@app.blob_output(arg_name="out", path="published/{id}.json", connection="Storage")
def publish_approved_package(msg: func.ServiceBusMessage, out: func.Out[str]):
    body = json.loads(msg.get_body().decode())
    if body.get("kind") == "approved":
        out.set(json.dumps({**body, "published_by": "luna-xi-functions"}, indent=1))


@app.service_bus_topic_trigger(arg_name="msg", topic_name="%SERVICEBUS_TOPIC%", subscription_name="notify", connection="ServiceBus")
def notify_editorial(msg: func.ServiceBusMessage):
    url = os.environ.get("LOGIC_APP_URL", "")
    if url:
        req = urllib.request.Request(url, method="POST", data=msg.get_body(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=20)


@app.timer_trigger(arg_name="timer", schedule="0 0 3 * * *", run_on_startup=False)
def nightly_quality_gate(timer: func.TimerRequest):
    api = os.environ.get("LUNA_API_URL", "").rstrip("/")
    if not api:
        return
    ok = 0
    cases = [("Who scored the second goal?", "T0"), ("Show me the sixth goal", "R"), ("Why did momentum change?", "T3")]
    for q, tier in cases:
        req = urllib.request.Request(f"{api}/api/ask", method="POST", data=json.dumps({"match_id": "m3-goal-festival", "question": q}).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                ok += json.loads(r.read())["tier"] == tier
        except Exception as e:  # noqa: BLE001
            logging.error("quality gate call failed: %s", e)
    logging.info("quality_gate routing_accuracy=%.2f", ok / len(cases))
