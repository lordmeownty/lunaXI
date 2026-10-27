"""Event Hubs (match events) + Service Bus (editorial workflow); in-memory outbox when not configured."""
from __future__ import annotations

import json
from collections import deque

from ..config import settings

outbox: deque = deque(maxlen=200)


def _credential():
    from azure.identity.aio import DefaultAzureCredential
    return DefaultAzureCredential()


async def publish_match_events(match_id: str, events: list[dict]) -> dict:
    if not (settings.eventhub_connection or settings.fully_qualified_namespace_eh):
        outbox.appendleft({"channel": "eventhub:" + settings.eventhub_name, "match_id": match_id, "count": len(events)})
        return {"mode": "outbox", "sent": len(events)}
    from azure.eventhub import EventData
    from azure.eventhub.aio import EventHubProducerClient
    producer = (EventHubProducerClient.from_connection_string(settings.eventhub_connection, eventhub_name=settings.eventhub_name)
                if settings.eventhub_connection else EventHubProducerClient(settings.fully_qualified_namespace_eh, settings.eventhub_name, _credential()))
    sent = 0
    async with producer:
        batch = await producer.create_batch(partition_key=match_id)
        for e in events:
            data = EventData(json.dumps({"match_id": match_id, **e}))
            try:
                batch.add(data)
            except ValueError:
                await producer.send_batch(batch)
                sent += len(batch)
                batch = await producer.create_batch(partition_key=match_id)
                batch.add(data)
        if len(batch):
            await producer.send_batch(batch)
            sent += len(batch)
    return {"mode": "eventhub", "sent": sent}


async def publish_package_event(kind: str, package: dict) -> dict:
    body = {k: package.get(k) for k in ("id", "match_id", "audience", "status", "title", "submitted_by", "decided_by", "recap")}
    body = {"kind": kind, "package_id": body.pop("id"), **body}
    if not (settings.servicebus_connection or settings.fully_qualified_namespace_sb):
        outbox.appendleft({"channel": "servicebus:" + settings.servicebus_topic, "kind": kind, "package_id": body["package_id"], "status": body["status"]})
        return {"mode": "outbox"}
    from azure.servicebus import ServiceBusMessage
    from azure.servicebus.aio import ServiceBusClient
    client = (ServiceBusClient.from_connection_string(settings.servicebus_connection) if settings.servicebus_connection
              else ServiceBusClient(settings.fully_qualified_namespace_sb, _credential()))
    async with client:
        async with client.get_topic_sender(settings.servicebus_topic) as sender:
            await sender.send_messages(ServiceBusMessage(json.dumps(body), subject=kind, application_properties={"kind": kind}))
    return {"mode": "servicebus"}
