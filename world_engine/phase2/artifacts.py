"""Build and write Phase 2 deployment artifacts.

This module generates the JSON and CSV files needed for the 10 Node-RED
floor gateways, the ThingsBoard import bundle, and the HiveMQ access-control
templates used by the Phase 2 hybrid deployment.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BUILDING_ID = "b01"
FLOOR_COUNT = 10
MQTT_NODES_PER_FLOOR = 10
COAP_NODES_PER_FLOOR = 10


def phase2_room_number(protocol: str, slot: int) -> int:
    """Return the Phase 2 room number for a protocol/slot pair."""
    base = 100 if protocol == "mqtt" else 200
    return base + slot


def phase2_room_id(floor: int, protocol: str, slot: int) -> str:
    """Return the canonical room identifier used across exports."""
    room_number = phase2_room_number(protocol, slot)
    return f"{BUILDING_ID}-f{floor:02d}-r{room_number:03d}"


def _device_token(floor: int, protocol: str, slot: int) -> str:
    return f"{BUILDING_ID}-f{floor:02d}-{protocol}-{slot:02d}-token"


def build_device_registry() -> list[dict[str, Any]]:
    """Generate the 200-device registry."""
    devices: list[dict[str, Any]] = []

    for floor in range(1, FLOOR_COUNT + 1):
        for slot in range(1, MQTT_NODES_PER_FLOOR + 1):
            room_number = phase2_room_number("mqtt", slot)
            device_id = phase2_room_id(floor, "mqtt", slot)
            devices.append(
                {
                    "name": device_id,
                    "label": f"MQTT Floor {floor:02d} Room {room_number:03d}",
                    "profile": "MQTT-ThermalSensor",
                    "protocol": "mqtt",
                    "floor": floor,
                    "room": room_number,
                    "telemetryTopic": f"campus/{BUILDING_ID}/f{floor:02d}/r{room_number:03d}/telemetry",
                    "commandTopic": f"campus/{BUILDING_ID}/f{floor:02d}/r{room_number:03d}/cmd",
                    "statusTopic": f"campus/{BUILDING_ID}/f{floor:02d}/r{room_number:03d}/status",
                    "deviceToken": _device_token(floor, "mqtt", slot),
                    "authType": "username_password",
                    "username": f"mqtt_{device_id}",
                    "password": f"pass_{floor:02d}_{slot:02d}",
                }
            )

        for slot in range(1, COAP_NODES_PER_FLOOR + 1):
            room_number = phase2_room_number("coap", slot)
            device_id = phase2_room_id(floor, "coap", slot)
            devices.append(
                {
                    "name": device_id,
                    "label": f"CoAP Floor {floor:02d} Room {room_number:03d}",
                    "profile": "CoAP-ThermalSensor",
                    "protocol": "coap",
                    "floor": floor,
                    "room": room_number,
                    "telemetryUri": f"coap://[node_ip]/f{floor:02d}/r{room_number:03d}/telemetry",
                    "commandUri": f"coap://[gateway_ip]/f{floor:02d}/r{room_number:03d}/actuators/hvac",
                    "statusTopic": f"campus/{BUILDING_ID}/f{floor:02d}/r{room_number:03d}/status",
                    "deviceToken": _device_token(floor, "coap", slot),
                    "authType": "psk",
                    "pskIdentity": f"coap_{device_id}",
                    "pskValue": f"psk-{floor:02d}-{slot:02d}",
                }
            )

    return devices


def build_asset_hierarchy() -> list[dict[str, Any]]:
    """Generate the Campus -> Building -> Floor -> Room asset hierarchy."""
    assets: list[dict[str, Any]] = [
        {"name": "Campus", "type": "campus", "externalId": "campus-b01"},
        {
            "name": f"Building {BUILDING_ID.upper()}",
            "type": "building",
            "externalId": f"building-{BUILDING_ID}",
            "parentExternalId": "campus-b01",
        },
    ]

    for floor in range(1, FLOOR_COUNT + 1):
        floor_external_id = f"floor-{floor:02d}"
        assets.append(
            {
                "name": f"Floor {floor:02d}",
                "type": "floor",
                "externalId": floor_external_id,
                "parentExternalId": f"building-{BUILDING_ID}",
            }
        )

        for protocol in ("mqtt", "coap"):
            for slot in range(1, MQTT_NODES_PER_FLOOR + 1):
                room_number = phase2_room_number(protocol, slot)
                assets.append(
                    {
                        "name": f"Room {room_number:03d}",
                        "type": "room",
                        "externalId": f"room-{BUILDING_ID}-f{floor:02d}-r{room_number:03d}",
                        "parentExternalId": floor_external_id,
                        "protocol": protocol,
                        "floor": floor,
                        "room": room_number,
                    }
                )

    return assets


def build_relations() -> list[dict[str, Any]]:
    """Generate asset and device relations for import."""
    relations: list[dict[str, Any]] = [
        {"from": "campus-b01", "to": "building-b01", "type": "Contains"},
    ]

    for floor in range(1, FLOOR_COUNT + 1):
        floor_external_id = f"floor-{floor:02d}"
        relations.append(
            {"from": "building-b01", "to": floor_external_id, "type": "Contains"}
        )

        for protocol in ("mqtt", "coap"):
            for slot in range(1, MQTT_NODES_PER_FLOOR + 1):
                room_number = phase2_room_number(protocol, slot)
                room_external_id = f"room-{BUILDING_ID}-f{floor:02d}-r{room_number:03d}"
                device_id = phase2_room_id(floor, protocol, slot)
                relations.append(
                    {"from": floor_external_id, "to": room_external_id, "type": "Contains"}
                )
                relations.append(
                    {"from": room_external_id, "to": device_id, "type": "Contains"}
                )

    return relations


def build_rule_chain() -> dict[str, Any]:
    """Generate a compact ThingsBoard rule-chain bundle."""
    return {
        "name": "Phase 2 Campus Rule Chain",
        "type": "ROOT",
        "nodes": [
            {
                "name": "Input",
                "type": "org.thingsboard.rule.engine.filter.TbMsgTypeNode",
                "script": "msgType == 'POST_TELEMETRY_REQUEST'",
            },
            {
                "name": "Normalize",
                "type": "org.thingsboard.rule.engine.transform.TbScriptNode",
                "script": (
                    "var payload = msg.get('payload');\n"
                    "var metadata = msg.get('metadata');\n"
                    "return { payload: payload, metadata: metadata, floor: metadata.floor };"
                ),
            },
            {
                "name": "Threshold Alarm",
                "type": "org.thingsboard.rule.engine.filter.TbJsFilterNode",
                "script": "return msg.payload.sensors && msg.payload.sensors.temperature > 28;",
            },
            {
                "name": "Create Alarm",
                "type": "org.thingsboard.rule.engine.action.TbCreateAlarmNode",
                "alarmType": "HIGH_TEMPERATURE",
            },
            {
                "name": "Route Telemetry",
                "type": "org.thingsboard.rule.engine.flow.TbRuleChainNode",
                "targetRuleChain": "Floor Telemetry Router",
            },
        ],
    }


def build_dashboard() -> dict[str, Any]:
    """Generate a simple dashboard export skeleton."""
    return {
        "title": "Phase 2 Fleet Health",
        "state": {
            "root": {
                "widgets": [
                    {
                        "type": "timeseries",
                        "title": "Campus Temperature",
                        "datasource": "telemetry",
                        "entityAlias": "allDevices",
                    },
                    {
                        "type": "alarmTable",
                        "title": "Active Alarms",
                        "datasource": "alarms",
                        "entityAlias": "allDevices",
                    },
                    {
                        "type": "latestValues",
                        "title": "Fleet Status Grid",
                        "datasource": "latestTelemetry",
                        "entityAlias": "allDevices",
                    },
                ]
            }
        },
        "aliases": {
            "allDevices": {
                "entityType": "DEVICE",
                "filter": {"type": "entityList", "entityList": ["MQTT-ThermalSensor", "CoAP-ThermalSensor"]},
            }
        },
    }


def build_gateway_flow(floor: int) -> list[dict[str, Any]]:
    """Generate a Node-RED flow for a floor gateway."""
    floor_tag = f"f{floor:02d}"
    mqtt_topic = f"campus/{BUILDING_ID}/{floor_tag}/+/telemetry"
    command_topic = f"campus/{BUILDING_ID}/{floor_tag}/+/cmd"

    return [
        {
            "id": f"tab-{floor_tag}",
            "type": "tab",
            "label": f"Floor {floor:02d} Gateway",
            "disabled": False,
            "info": "MQTT and CoAP gateway for one campus floor.",
        },
        {
            "id": f"mqtt-in-{floor_tag}",
            "type": "mqtt in",
            "z": f"tab-{floor_tag}",
            "name": "MQTT telemetry",
            "topic": mqtt_topic,
            "qos": "1",
            "datatype": "auto",
            "broker": f"mqtt-broker-{floor_tag}",
            "nl": False,
            "rap": True,
            "rh": 0,
            "x": 160,
            "y": 120,
            "wires": [[f"normalize-mqtt-{floor_tag}"]],
        },
        {
            "id": f"coap-in-{floor_tag}",
            "type": "coap-in",
            "z": f"tab-{floor_tag}",
            "name": "CoAP observe",
            "url": f"coap://[node_ip]/f{floor:02d}/r201/telemetry",
            "method": "observe",
            "observe": True,
            "x": 160,
            "y": 200,
            "wires": [[f"normalize-coap-{floor_tag}"]],
        },
        {
            "id": f"normalize-mqtt-{floor_tag}",
            "type": "function",
            "z": f"tab-{floor_tag}",
            "name": "Normalize MQTT payload",
            "func": (
                "const data = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload;\n"
                "msg.payload = { protocol: 'mqtt', source: data.metadata.sensor_id, data };\n"
                "return msg;"
            ),
            "outputs": 1,
            "x": 410,
            "y": 120,
            "wires": [[f"floor-merge-{floor_tag}"]],
        },
        {
            "id": f"normalize-coap-{floor_tag}",
            "type": "function",
            "z": f"tab-{floor_tag}",
            "name": "Normalize CoAP payload",
            "func": (
                "const data = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload;\n"
                "msg.payload = { protocol: 'coap', source: data.metadata.sensor_id, data };\n"
                "return msg;"
            ),
            "outputs": 1,
            "x": 410,
            "y": 200,
            "wires": [[f"floor-merge-{floor_tag}"]],
        },
        {
            "id": f"floor-merge-{floor_tag}",
            "type": "join",
            "z": f"tab-{floor_tag}",
            "name": "Merge streams",
            "mode": "auto",
            "build": "array",
            "property": "payload",
            "x": 640,
            "y": 160,
            "wires": [[f"floor-average-{floor_tag}"]],
        },
        {
            "id": f"floor-average-{floor_tag}",
            "type": "function",
            "z": f"tab-{floor_tag}",
            "name": "60s floor average",
            "func": (
                "const windowMs = 60000;\n"
                "const now = Date.now();\n"
                "const history = flow.get('history') || [];\n"
                "const items = (Array.isArray(msg.payload) ? msg.payload : [msg.payload]).filter(Boolean);\n"
                "for (const item of items) { history.push({ ts: now, item }); }\n"
                "const recent = history.filter(entry => now - entry.ts <= windowMs);\n"
                "flow.set('history', recent);\n"
                "const temps = recent.map(entry => entry.item?.data?.sensors?.temperature).filter(v => typeof v === 'number');\n"
                "const hums = recent.map(entry => entry.item?.data?.sensors?.humidity).filter(v => typeof v === 'number');\n"
                "const avg = arr => arr.length ? arr.reduce((sum, value) => sum + value, 0) / arr.length : 0;\n"
                "msg.payload = {\n"
                "  floor: '" + floor_tag + "',\n"
                "  timestamp: now,\n"
                "  windowSeconds: 60,\n"
                "  temperatureAvg: Number(avg(temps).toFixed(2)),\n"
                "  humidityAvg: Number(avg(hums).toFixed(2)),\n"
                "  sampleCount: recent.length\n"
                "};\n"
                "return msg;"
            ),
            "outputs": 1,
            "x": 870,
            "y": 160,
            "wires": [[f"mqtt-out-summary-{floor_tag}"]],
        },
        {
            "id": f"mqtt-out-summary-{floor_tag}",
            "type": "mqtt out",
            "z": f"tab-{floor_tag}",
            "name": "Publish floor summary",
            "topic": f"campus/{BUILDING_ID}/{floor_tag}/summary",
            "qos": "1",
            "retain": True,
            "broker": f"mqtt-broker-{floor_tag}",
            "x": 1110,
            "y": 160,
            "wires": [],
        },
        {
            "id": f"cmd-in-{floor_tag}",
            "type": "mqtt in",
            "z": f"tab-{floor_tag}",
            "name": "Command listen",
            "topic": command_topic,
            "qos": "2",
            "datatype": "auto",
            "broker": f"mqtt-broker-{floor_tag}",
            "x": 160,
            "y": 300,
            "wires": [[f"cmd-router-{floor_tag}"]],
        },
        {
            "id": f"cmd-router-{floor_tag}",
            "type": "function",
            "z": f"tab-{floor_tag}",
            "name": "MQTT to CoAP PUT",
            "func": (
                "const cmd = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload;\n"
                "msg.method = 'put';\n"
                "msg.payload = JSON.stringify(cmd);\n"
                f"msg.url = 'coap://[gateway_ip]/f{floor:02d}/r201/actuators/hvac';\n"
                "return msg;"
            ),
            "outputs": 1,
            "x": 430,
            "y": 300,
            "wires": [[f"coap-put-{floor_tag}"]],
        },
        {
            "id": f"coap-put-{floor_tag}",
            "type": "coap request",
            "z": f"tab-{floor_tag}",
            "name": "CoAP PUT actuator",
            "url": f"coap://[gateway_ip]/f{floor:02d}/r201/actuators/hvac",
            "method": "put",
            "confirmable": True,
            "x": 680,
            "y": 300,
            "wires": [[f"mqtt-out-response-{floor_tag}"]],
        },
        {
            "id": f"mqtt-out-response-{floor_tag}",
            "type": "mqtt out",
            "z": f"tab-{floor_tag}",
            "name": "Command response",
            "topic": f"campus/{BUILDING_ID}/{floor_tag}/response",
            "qos": "1",
            "retain": False,
            "broker": f"mqtt-broker-{floor_tag}",
            "x": 960,
            "y": 300,
            "wires": [],
        },
        {
            "id": f"mqtt-broker-{floor_tag}",
            "type": "mqtt-broker",
            "name": "HiveMQ Backbone",
            "broker": "hivemq",
            "port": "1883",
            "clientid": f"gateway-{floor_tag}",
            "usetls": False,
            "keepalive": "60",
            "cleansession": True,
            "protocolVersion": "5",
        },
    ]


def build_hivemq_acl() -> str:
    """Return an ACL file that isolates each floor's topics."""
    lines = ["# HiveMQ ACL template for Phase 2", "# Replace usernames with provisioned node identities"]
    for floor in range(1, FLOOR_COUNT + 1):
        floor_tag = f"f{floor:02d}"
        lines.extend(
            [
                f"user floor-{floor_tag}-mqtt",
                f"topic readwrite campus/{BUILDING_ID}/{floor_tag}/#",
                f"topic read campus/{BUILDING_ID}/fleet/#",
                f"user floor-{floor_tag}-gateway",
                f"topic read campus/{BUILDING_ID}/{floor_tag}/#",
                f"topic write campus/{BUILDING_ID}/{floor_tag}/summary",
            ]
        )
    return "\n".join(lines) + "\n"


def build_security_manifest() -> dict[str, Any]:
    """Generate a compact certificate/PSK manifest for the docs."""
    return {
        "mqtt": {
            "tlsPort": 8883,
            "certificate": "docker/certs/mqtt-server.crt",
            "privateKey": "docker/certs/mqtt-server.key",
            "caBundle": "docker/certs/ca.crt",
        },
        "coap": {
            "dtlsPort": 5684,
            "pskFile": "docker/certs/coap-psk.json",
            "pskTemplate": {
                "identity": "coap-b01-f01-r201",
                "secret": "psk-b01-f01-r201",
            },
        },
    }


def build_report_data() -> dict[str, Any]:
    """Collect the key submission data used by the report prompt."""
    return {
        "topology": {
            "floors": FLOOR_COUNT,
            "mqttNodes": FLOOR_COUNT * MQTT_NODES_PER_FLOOR,
            "coapNodes": FLOOR_COUNT * COAP_NODES_PER_FLOOR,
            "gateways": FLOOR_COUNT,
            "protocolSplitPerGateway": {"mqtt": 10, "coap": 10},
        },
        "messaging": {
            "mqttTelemetryTopic": f"campus/{BUILDING_ID}/f##/r###/telemetry",
            "mqttCommandTopic": f"campus/{BUILDING_ID}/f##/r###/cmd",
            "coapTelemetryUri": "coap://[node_ip]/f##/r###/telemetry",
            "coapCommandUri": "coap://[gateway_ip]/f##/r###/actuators/hvac",
            "mqttCommandQoS": 2,
            "coapAlertType": "CON",
        },
        "reliability": {
            "duplicateStrategy": "Idempotency keys with command_id plus floor-local dedup cache",
            "heartbeatTimeoutSeconds": 60,
            "coapDeadThresholdSeconds": 60,
            "summaryWindowSeconds": 60,
        },
        "security": build_security_manifest(),
        "performanceTargets": {
            "rttTargetMs": 500,
            "mqttClientsTarget": 100,
            "packetLossTarget": 0,
        },
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_phase2_artifacts(output_root: str | Path) -> dict[str, Path]:
    """Write all Phase 2 artifacts to disk and return the created paths."""
    root = Path(output_root)
    created: dict[str, Path] = {}

    devices = build_device_registry()
    assets = build_asset_hierarchy()
    relations = build_relations()
    rule_chain = build_rule_chain()
    dashboard = build_dashboard()
    report_data = build_report_data()

    write_csv(root / "thingsboard" / "devices.csv", devices)
    write_json(root / "thingsboard" / "devices.json", devices)
    write_json(root / "thingsboard" / "assets.json", assets)
    write_json(root / "thingsboard" / "relations.json", relations)
    write_json(root / "thingsboard" / "rule-chain.json", rule_chain)
    write_json(root / "thingsboard" / "dashboard.json", dashboard)
    write_json(root / "phase2-report-data.json", report_data)
    write_json(root / "security" / "hivemq-cert-manifest.json", report_data["security"])

    acl_text = build_hivemq_acl()
    acl_path = root / "security" / "hivemq-acl.txt"
    acl_path.parent.mkdir(parents=True, exist_ok=True)
    acl_path.write_text(acl_text, encoding="utf-8")

    for floor in range(1, FLOOR_COUNT + 1):
        flow = build_gateway_flow(floor)
        flow_path = root / "node-red" / f"floor-{floor:02d}-gateway.json"
        write_json(flow_path, flow)
        created[f"node_red_floor_{floor:02d}"] = flow_path

    created["devices_csv"] = root / "thingsboard" / "devices.csv"
    created["devices_json"] = root / "thingsboard" / "devices.json"
    created["assets_json"] = root / "thingsboard" / "assets.json"
    created["relations_json"] = root / "thingsboard" / "relations.json"
    created["rule_chain_json"] = root / "thingsboard" / "rule-chain.json"
    created["dashboard_json"] = root / "thingsboard" / "dashboard.json"
    created["acl_txt"] = acl_path
    created["report_data_json"] = root / "phase2-report-data.json"

    return created