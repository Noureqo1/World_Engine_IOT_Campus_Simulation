"""Hybrid Phase 2 runtime for 100 MQTT nodes and 100 CoAP nodes.

The runtime is intentionally split from the Phase 1 engine so the campus
simulation can be launched in either mode. Phase 2 keeps the thermal model
from Phase 1 but fans it out over gmqtt and aiocoap transport layers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from world_engine.core.models import HVACMode, Room
from world_engine.utils.config import load_config

logger = logging.getLogger(__name__)

try:  # Optional dependency guard for development environments
    from gmqtt import Client as GMQTTClient
except ImportError:  # pragma: no cover - runtime guard only
    GMQTTClient = None

try:  # Optional dependency guard for development environments
    import aiomqtt
except ImportError:  # pragma: no cover - runtime guard only
    aiomqtt = None

try:  # Optional dependency guard for development environments
    from aiocoap import Context, Message, Code
    from aiocoap.resource import ObservableResource, Resource, Site
except ImportError:  # pragma: no cover - runtime guard only
    Context = None
    Message = None
    Code = None
    ObservableResource = object
    Resource = object
    Site = None


@dataclass(slots=True)
class Phase2Config:
    """Configuration for the Phase 2 hybrid engine."""

    building_id: str = "b01"
    floors: int = 10
    mqtt_nodes_per_floor: int = 10
    coap_nodes_per_floor: int = 10
    mqtt_host: str = "hivemq"
    mqtt_port: int = 1883
    mqtt_tls_port: int = 8883
    coap_bind_host: str = "0.0.0.0"
    coap_start_port: int = 5683
    tick_interval: float = 5.0
    startup_jitter_max: float = 2.0
    command_qos: int = 2
    edge_summary_window_seconds: int = 60
    heartbeat_timeout_seconds: int = 60
    dedup_cache_ttl_seconds: int = 30
    mqtt_username_prefix: str = "mqtt_"
    mqtt_password_prefix: str = "pass_"
    psk_prefix: str = "psk-"
    direct_tb_mqtt_transport: bool = False
    tb_telemetry_topic: str = "v1/devices/me/telemetry"
    tb_rpc_request_topic: str = "v1/devices/me/rpc/request/+"
    tb_rpc_response_topic_prefix: str = "v1/devices/me/rpc/response/"
    tb_enable_rpc: bool = False
    tb_access_token_pattern: str = "{building}-f{floor:02d}-mqtt-{slot:02d}-token"
    tb_sync_access_tokens_from_api: bool = False
    tb_api_base_url: str = "http://thingsboard:9090"
    tb_tenant_username: str = "tenant@thingsboard.org"
    tb_tenant_password: str = "tenant"

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "Phase2Config":
        phase2 = config.get("phase2", {})
        phase2_network = phase2.get("network", {})
        phase2_security = phase2.get("security", {})
        phase2_tb = phase2.get("thingsboard", {})

        return cls(
            building_id=config.get("building", {}).get("id", "b01"),
            floors=phase2.get("floors", config.get("building", {}).get("floors", 10)),
            mqtt_nodes_per_floor=phase2.get("mqtt_nodes_per_floor", 10),
            coap_nodes_per_floor=phase2.get("coap_nodes_per_floor", 10),
            mqtt_host=phase2_network.get("mqtt_host", config.get("mqtt", {}).get("broker_host", "hivemq")),
            mqtt_port=phase2_network.get("mqtt_port", config.get("mqtt", {}).get("broker_port", 1883)),
            mqtt_tls_port=phase2_network.get("mqtt_tls_port", 8883),
            coap_bind_host=phase2_network.get("coap_bind_host", "0.0.0.0"),
            coap_start_port=phase2_network.get("coap_start_port", 5683),
            tick_interval=config.get("simulation", {}).get("tick_interval", 5.0),
            startup_jitter_max=config.get("simulation", {}).get("startup_jitter_max", 2.0),
            command_qos=phase2.get("command_qos", 2),
            edge_summary_window_seconds=phase2.get("edge_summary_window_seconds", 60),
            heartbeat_timeout_seconds=phase2.get("heartbeat_timeout_seconds", 60),
            dedup_cache_ttl_seconds=phase2.get("dedup_cache_ttl_seconds", 30),
            mqtt_username_prefix=phase2_security.get("mqtt_username_prefix", "mqtt_"),
            mqtt_password_prefix=phase2_security.get("mqtt_password_prefix", "pass_"),
            psk_prefix=phase2_security.get("psk_prefix", "psk-"),
            direct_tb_mqtt_transport=phase2_tb.get("direct_mqtt_transport", False),
            tb_telemetry_topic=phase2_tb.get("telemetry_topic", "v1/devices/me/telemetry"),
            tb_rpc_request_topic=phase2_tb.get("rpc_request_topic", "v1/devices/me/rpc/request/+"),
            tb_rpc_response_topic_prefix=phase2_tb.get("rpc_response_topic_prefix", "v1/devices/me/rpc/response/"),
            tb_enable_rpc=phase2_tb.get("enable_rpc", False),
            tb_access_token_pattern=phase2_tb.get(
                "access_token_pattern",
                "{building}-f{floor:02d}-mqtt-{slot:02d}-token",
            ),
            tb_sync_access_tokens_from_api=phase2_tb.get("sync_access_tokens_from_api", False),
            tb_api_base_url=phase2_tb.get("api_base_url", "http://thingsboard:9090"),
            tb_tenant_username=phase2_tb.get("tenant_username", "tenant@thingsboard.org"),
            tb_tenant_password=phase2_tb.get("tenant_password", "tenant"),
        )


@dataclass(slots=True)
class HybridNode:
    """A single simulated endpoint in the hybrid campus."""

    room: Room
    protocol: str
    floor: int
    slot: int
    port: int | None = None
    client_id: str | None = None
    username: str | None = None
    password: str | None = None
    access_token: str | None = None
    psk_identity: str | None = None
    psk_secret: str | None = None

    @property
    def command_nonce_key(self) -> str:
        return f"{self.room.room_id}:{self.protocol}"


class _ThermalTelemetryResource(ObservableResource):
    """Observable CoAP telemetry resource tied to one simulated room."""

    def __init__(self, node: HybridNode):
        super().__init__()
        self.node = node
        self._last_payload = self._encode_payload()

    def _encode_payload(self) -> bytes:
        payload = self.node.room.to_telemetry_payload()
        payload["transport"] = "coap"
        payload["protocol"] = "coap"
        payload["metadata"]["command_nonce"] = self.node.command_nonce_key
        return json.dumps(payload).encode("utf-8")

    def refresh(self) -> None:
        self._last_payload = self._encode_payload()
        self.updated_state()

    async def render_get(self, request):  # type: ignore[override]
        return Message(payload=self._last_payload, content_format=50)


class _ThermalHVACResource(Resource):
    """CoAP actuator endpoint that accepts PUT commands."""

    def __init__(self, node: HybridNode, telemetry_resource: _ThermalTelemetryResource):
        super().__init__()
        self.node = node
        self.telemetry_resource = telemetry_resource

    async def render_put(self, request):  # type: ignore[override]
        raw = request.payload.decode("utf-8") if request.payload else "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"command": raw}

        command_id = str(payload.get("command_id") or payload.get("nonce") or hash(raw))
        if getattr(self.node.room, "_last_command_id", None) == command_id:
            logger.info("Ignoring duplicate CoAP command for %s", self.node.room.room_id)
            return Message(code=Code.CHANGED, payload=b"duplicate")

        self.node.room._last_command_id = command_id  # idempotency cache for duplicates

        hvac_enabled = payload.get("hvac_active")
        if hvac_enabled is None:
            hvac_enabled = payload.get("toggle", "on").lower() not in {"off", "false", "0"}

        self.node.room.hvac_mode = HVACMode.ON if hvac_enabled else HVACMode.OFF
        self.telemetry_resource.refresh()

        response = {
            "room": self.node.room.room_id,
            "ack": True,
            "command_id": command_id,
            "hvac_active": hvac_enabled,
            "timestamp": int(time.time()),
        }
        return Message(code=Code.CHANGED, payload=json.dumps(response).encode("utf-8"), content_format=50)


class HybridWorldEngine:
    """Async hybrid engine for MQTT + CoAP campus nodes."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.phase2 = Phase2Config.from_dict(config)
        self._shutdown_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self._seen_commands: dict[str, dict[str, float]] = {}
        self._coap_contexts: list[Any] = []

    def _tb_api_request(self, method: str, path: str, token: str | None = None) -> dict[str, Any]:
        base = self.phase2.tb_api_base_url.rstrip("/")
        url = f"{base}{path}"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url=url, method=method, headers=headers)
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _resolve_access_tokens_from_thingsboard(self, mqtt_nodes: list[HybridNode]) -> None:
        if not self.phase2.tb_sync_access_tokens_from_api:
            return

        try:
            login_payload = json.dumps(
                {
                    "username": self.phase2.tb_tenant_username,
                    "password": self.phase2.tb_tenant_password,
                }
            ).encode("utf-8")
            base = self.phase2.tb_api_base_url.rstrip("/")
            login_request = urllib.request.Request(
                url=f"{base}/api/auth/login",
                data=login_payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(login_request, timeout=10) as response:
                login = json.loads(response.read().decode("utf-8"))
            token = login.get("token")
            if not token:
                logger.warning("ThingsBoard token sync skipped: login returned no token")
                return

            synced = 0
            for node in mqtt_nodes:
                query = urllib.parse.quote(node.room.room_id)
                device = self._tb_api_request(
                    "GET",
                    f"/api/tenant/devices?deviceName={query}",
                    token=token,
                )
                device_id = device.get("id", {}).get("id")
                if not device_id:
                    continue
                credentials = self._tb_api_request(
                    "GET",
                    f"/api/device/{device_id}/credentials",
                    token=token,
                )
                access_token = credentials.get("credentialsId")
                if access_token:
                    node.access_token = access_token
                    synced += 1
            logger.info("ThingsBoard token sync complete: %s/%s MQTT nodes", synced, len(mqtt_nodes))
        except Exception as exc:
            logger.warning("ThingsBoard token sync failed, using configured token pattern: %s", exc)

    def build_nodes(self) -> tuple[list[HybridNode], list[HybridNode]]:
        """Create the 100 MQTT nodes and 100 CoAP nodes for the campus."""
        mqtt_nodes: list[HybridNode] = []
        coap_nodes: list[HybridNode] = []

        physics = {
            "k_env": self.config.get("physics", {}).get("k_env", 0.01),
            "k_hvac": self.config.get("physics", {}).get("k_hvac", 0.2),
        }

        for floor in range(1, self.phase2.floors + 1):
            for slot in range(1, self.phase2.mqtt_nodes_per_floor + 1):
                room_number = 100 + slot
                room = Room(
                    building=self.phase2.building_id,
                    floor=floor,
                    room_number=room_number,
                    protocol="mqtt",
                    k_env=physics["k_env"],
                    k_hvac=physics["k_hvac"],
                    outside_temp=self.config.get("simulation", {}).get("outside_temperature", 15.0),
                )
                mqtt_nodes.append(
                    HybridNode(
                        room=room,
                        protocol="mqtt",
                        floor=floor,
                        slot=slot,
                        client_id=f"{self.phase2.building_id}-f{floor:02d}-mqtt-{slot:02d}",
                        username=f"{self.phase2.mqtt_username_prefix}{room.room_id}",
                        password=f"{self.phase2.mqtt_password_prefix}{floor:02d}_{slot:02d}",
                        access_token=self.phase2.tb_access_token_pattern.format(
                            building=self.phase2.building_id,
                            floor=floor,
                            slot=slot,
                        ),
                    )
                )

            for slot in range(1, self.phase2.coap_nodes_per_floor + 1):
                room_number = 200 + slot
                room = Room(
                    building=self.phase2.building_id,
                    floor=floor,
                    room_number=room_number,
                    protocol="coap",
                    k_env=physics["k_env"],
                    k_hvac=physics["k_hvac"],
                    outside_temp=self.config.get("simulation", {}).get("outside_temperature", 15.0),
                )
                coap_nodes.append(
                    HybridNode(
                        room=room,
                        protocol="coap",
                        floor=floor,
                        slot=slot,
                        port=self.phase2.coap_start_port + len(coap_nodes),
                        psk_identity=f"coap_{room.room_id}",
                        psk_secret=f"{self.phase2.psk_prefix}{floor:02d}-{slot:02d}",
                    )
                )

        return mqtt_nodes, coap_nodes

    async def _publish_mqtt(self, client: Any, node: HybridNode) -> None:
        payload = node.room.to_telemetry_payload()
        payload["transport"] = "mqtt"
        payload["protocol"] = "mqtt"
        if self.phase2.direct_tb_mqtt_transport:
            # ThingsBoard expects flat telemetry key-values on v1/devices/me/telemetry.
            telemetry = {
                "temperature": payload["sensors"]["temperature"],
                "humidity": payload["sensors"]["humidity"],
                "occupancy": payload["sensors"]["occupancy"],
                "light_level": payload["sensors"]["light_level"],
                "hvac_mode": payload["actuators"]["hvac_mode"],
            }
            await client.publish(self.phase2.tb_telemetry_topic, json.dumps(telemetry), qos=1)
            return
        await client.publish(node.room.phase2_mqtt_topic, json.dumps(payload), qos=1)

    def _dedup_key(self, node: HybridNode, command: dict[str, Any]) -> tuple[str, str]:
        command_id = str(command.get("command_id") or command.get("nonce") or hash(json.dumps(command, sort_keys=True)))
        return node.command_nonce_key, command_id

    def _mark_seen(self, node_key: str, command_id: str) -> bool:
        now = time.time()
        cache = self._seen_commands.setdefault(node_key, {})
        expired = [command_id for command_id, timestamp in cache.items() if now - timestamp > self.phase2.dedup_cache_ttl_seconds]
        for expired_command_id in expired:
            cache.pop(expired_command_id, None)
        if command_id in cache:
            return False
        cache[command_id] = now
        return True

    async def _run_mqtt_node(self, node: HybridNode) -> None:
        if self.phase2.direct_tb_mqtt_transport:
            if aiomqtt is None:
                raise RuntimeError("aiomqtt is required for direct ThingsBoard MQTT transport")
            async with aiomqtt.Client(
                hostname=self.phase2.mqtt_host,
                port=self.phase2.mqtt_port,
                identifier=node.client_id or node.room.room_id,
                username=node.access_token,
                password="",
            ) as client:
                logger.info("MQTT node connected: %s", node.room.room_id)
                while not self._shutdown_event.is_set():
                    node.room.set_outside_temp(self.config.get("simulation", {}).get("outside_temperature", 15.0))
                    node.room.update_physics()
                    await self._publish_mqtt(client, node)
                    await asyncio.sleep(self.phase2.tick_interval)
            return

        if GMQTTClient is None:
            raise RuntimeError("gmqtt is required for Phase 2 MQTT nodes")

        client = GMQTTClient(node.client_id or node.room.room_id)

        def on_connect(_client, _flags, _rc, _properties=None):
            logger.info("MQTT node connected: %s", node.room.room_id)
            if self.phase2.direct_tb_mqtt_transport:
                if not self.phase2.tb_enable_rpc:
                    return
                return _client.subscribe(self.phase2.tb_rpc_request_topic, qos=self.phase2.command_qos)
            return _client.subscribe(node.room.phase2_command_topic, qos=self.phase2.command_qos)

        async def on_message(_client, _topic, payload, _qos, _properties=None):
            raw = payload.decode("utf-8") if isinstance(payload, (bytes, bytearray)) else str(payload)
            try:
                command = json.loads(raw)
            except json.JSONDecodeError:
                command = {"command": raw}

            if self.phase2.direct_tb_mqtt_transport:
                method = str(command.get("method", "")).lower()
                params = command.get("params", {})
                if not isinstance(params, dict):
                    params = {}
                command = {
                    "command_id": _topic.rsplit("/", maxsplit=1)[-1],
                    "hvac_active": params.get("hvac_active", params.get("enabled", method != "turnoff")),
                }

            node_key, command_id = self._dedup_key(node, command)
            if not self._mark_seen(node_key, command_id):
                logger.info("Duplicate MQTT command ignored for %s", node.room.room_id)
                return
            hvac_active = command.get("hvac_active")
            if hvac_active is None:
                hvac_active = str(command.get("toggle", "on")).lower() not in {"off", "false", "0"}
            node.room.hvac_mode = HVACMode.ON if hvac_active else HVACMode.OFF
            ack = {
                "room": node.room.room_id,
                "ack": True,
                "command_id": command.get("command_id") or command.get("nonce") or command_id,
                "transport": "mqtt",
                "timestamp": int(time.time()),
            }
            if self.phase2.direct_tb_mqtt_transport:
                response_topic = f"{self.phase2.tb_rpc_response_topic_prefix}{ack['command_id']}"
                await _client.publish(response_topic, json.dumps({"success": True, "ack": ack}), qos=1)
            else:
                await _client.publish(f"{node.room.phase2_command_topic}/response", json.dumps(ack), qos=1)

        client.on_connect = on_connect
        client.on_message = on_message
        if self.phase2.direct_tb_mqtt_transport:
            client.set_auth_credentials(node.access_token, "")
        else:
            client.set_auth_credentials(node.username, node.password)
            client.set_last_will(
                node.room.phase2_status_topic,
                json.dumps({"room": node.room.room_id, "status": "offline"}),
                qos=1,
                retain=True,
            )

        await client.connect(self.phase2.mqtt_host, self.phase2.mqtt_port)
        try:
            while not self._shutdown_event.is_set():
                node.room.set_outside_temp(self.config.get("simulation", {}).get("outside_temperature", 15.0))
                node.room.update_physics()
                payload = node.room.to_telemetry_payload()
                payload["transport"] = "mqtt"
                payload["protocol"] = "mqtt"
                payload["command_qos"] = self.phase2.command_qos
                await self._publish_mqtt(client, node)
                await asyncio.sleep(self.phase2.tick_interval)
        finally:
            await client.disconnect()

    async def _run_coap_node(self, node: HybridNode) -> None:
        if Context is None or Site is None:
            raise RuntimeError("aiocoap is required for Phase 2 CoAP nodes")

        site = Site()
        telemetry_resource = _ThermalTelemetryResource(node)
        site.add_resource((f"f{node.floor:02d}", f"r{node.room.room_number:03d}", "telemetry"), telemetry_resource)
        site.add_resource((f"f{node.floor:02d}", f"r{node.room.room_number:03d}", "actuators", "hvac"), _ThermalHVACResource(node, telemetry_resource))

        context = await Context.create_server_context(site, bind=(self.phase2.coap_bind_host, node.port or self.phase2.coap_start_port))
        self._coap_contexts.append(context)
        logger.info("CoAP node bound: %s on UDP port %s", node.room.room_id, node.port)

        try:
            while not self._shutdown_event.is_set():
                node.room.set_outside_temp(self.config.get("simulation", {}).get("outside_temperature", 15.0))
                node.room.update_physics()
                telemetry_resource.refresh()
                await asyncio.sleep(self.phase2.tick_interval)
        finally:
            await context.shutdown()

    async def run(self) -> None:
        """Launch the hybrid runtime."""
        mqtt_nodes, coap_nodes = self.build_nodes()
        self._resolve_access_tokens_from_thingsboard(mqtt_nodes)

        logger.info(
            "Launching Phase 2: %s MQTT nodes, %s CoAP nodes, %s gateways",
            len(mqtt_nodes),
            len(coap_nodes),
            self.phase2.floors,
        )

        self._tasks = [asyncio.create_task(self._run_mqtt_node(node), name=node.room.room_id) for node in mqtt_nodes]
        self._tasks.extend(asyncio.create_task(self._run_coap_node(node), name=f"{node.room.room_id}-coap") for node in coap_nodes)

        try:
            await self._shutdown_event.wait()
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Stop all tasks and cleanly disconnect from transport layers."""
        if self._shutdown_event.is_set() is False:
            self._shutdown_event.set()

        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        for context in self._coap_contexts:
            try:
                await context.shutdown()
            except Exception:  # pragma: no cover - best effort cleanup
                logger.exception("Failed to shut down CoAP context")


def load_phase2_config(config_path: str = "config.phase2.yaml") -> dict[str, Any]:
    """Load a Phase 2 config file with a fallback to the shared config."""
    path = Path(config_path)
    if path.exists():
        return load_config(str(path))
    return load_config("config.yaml")