"""Setting a heat pump up: local first, the cloud only for what is missing.

The flow searches the local network before it asks anything: an EMS-ESP
gateway first, then a Husdata interface. What it finds is shown and ticked;
an EMS-ESP gateway asks for its web login so it can write (skipping leaves it
read only). Only then is Bosch's cloud offered - to fill in what the local
sources lack, or as the way in when nothing was found locally. Typing an
address in is always on the menu.

A source can be added later from the options (Configure): another local
source by its address, or the cloud by logging in, which is how a pump set up
on its EMS-ESP gateway gets its K30 alongside.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import voluptuous as vol

from .const import (
    CIRCUITS,
    CONF_BRAND,
    CONF_CLOUD_SCAN_INTERVAL,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_KIND,
    CONF_MODE_CIRCUITS,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    CONF_STEP_BLOCKED,
    CONF_STEP_BOOST,
    CONF_STEP_ECO,
    CONF_TOKEN,
    CONF_USERNAME,
    DEFAULT_CLOUD_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SOURCE_CLOUD,
    SOURCE_EMSESP,
    SOURCE_PRIORITY,
)
from .emsesp import EmsEspSource
from .heating_mode import DEFAULT_STEPS
from .model import AuthError, SourceError
from .scanner import Found, async_find, async_identify

_LOGGER = logging.getLogger(__name__)

PASSWORD = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))


def _configured(hass, kind: str, host: str | None = None, device_id: str | None = None) -> bool:
    """Whether a source is already part of some installation."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        for conf in entry.data.get(CONF_SOURCES, []):
            if conf.get(CONF_KIND) != kind:
                continue
            if host is not None and conf.get(CONF_HOST) == host:
                return True
            if device_id is not None and str(conf.get(CONF_DEVICE_ID)) == str(device_id):
                return True
    return False


async def _emsesp_token(hass, host: str, username: str, password: str, token: str) -> dict[str, Any]:
    """The login fields to store for an EMS-ESP gateway; raises AuthError/SourceError."""
    if not (username or password or token):
        return {}
    client = EmsEspSource(
        async_get_clientsession(hass), host, token=token or None, username=username or None, password=password or None
    )
    if not token:
        token = await client.async_sign_in()
    out: dict[str, Any] = {CONF_TOKEN: token}
    if username and password:
        out[CONF_USERNAME] = username
        out[CONF_PASSWORD] = password
    return out


class _CloudLogin:
    """The cloud's three steps, shared by the setup flow and the options flow."""

    _cloud: dict[str, Any] | None

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Which brand's login page: IVT owners use Bosch's."""
        if user_input is not None:
            from .bosch_cloud import new_login

            self._cloud = new_login(user_input.get(CONF_BRAND, "bosch"))
            return await self.async_step_cloud_code()
        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BRAND, default="bosch"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["bosch", "buderus"], translation_key="brand", mode=selector.SelectSelectorMode.LIST
                        )
                    )
                }
            ),
        )

    async def async_step_cloud_code(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Log in in a browser tab, then paste what it shows."""
        from .bosch_cloud import async_exchange, async_gateways, code_from, new_login

        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                tokens = await async_exchange(
                    session, code_from(user_input["code"]), self._cloud["verifier"], self._cloud["brand"]
                )
                gateways = await async_gateways(session, tokens["access_token"])
            except AuthError:
                errors["base"] = "invalid_code"
                # A code is single use and short lived: a new try needs a new link.
                self._cloud = new_login(self._cloud["brand"])
            except SourceError:
                errors["base"] = "cannot_connect"
            else:
                self._cloud["tokens"] = tokens
                self._cloud["gateways"] = gateways
                if not gateways:
                    return self.async_abort(reason="no_gateways")
                if len(gateways) == 1:
                    return await self._async_cloud_gateway(gateways[0])
                return await self.async_step_cloud_pick()
        return self.async_show_form(
            step_id="cloud_code",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
            description_placeholders={"url": self._cloud["url"]},
        )

    async def async_step_cloud_pick(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        gateways = self._cloud["gateways"]
        if user_input is not None:
            chosen = next(g for g in gateways if str(g["deviceId"]) == user_input[CONF_DEVICE_ID])
            return await self._async_cloud_gateway(chosen)
        options = [
            selector.SelectOptionDict(
                value=str(g["deviceId"]), label=f"{str(g.get('deviceType', '')).upper()} {g['deviceId']}"
            )
            for g in gateways
        ]
        return self.async_show_form(
            step_id="cloud_pick",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE_ID): selector.SelectSelector(selector.SelectSelectorConfig(options=options))}
            ),
        )

    async def _async_cloud_gateway(self, gateway: dict[str, Any]) -> ConfigFlowResult:
        tokens = self._cloud["tokens"]
        conf = {
            CONF_KIND: SOURCE_CLOUD,
            CONF_DEVICE_ID: str(gateway["deviceId"]),
            "device_type": gateway.get("deviceType"),
            CONF_BRAND: self._cloud["brand"],
            CONF_TOKEN: tokens["access_token"],
            CONF_REFRESH_TOKEN: tokens.get("refresh_token"),
            "unique_id": f"cloud-{gateway['deviceId']}",
        }
        self._cloud = None
        if _configured(self.hass, SOURCE_CLOUD, device_id=conf[CONF_DEVICE_ID]):
            return self.async_abort(reason="already_configured")
        return await self._async_cloud_chosen(conf)

    async def _async_cloud_chosen(self, conf: dict[str, Any]) -> ConfigFlowResult:
        raise NotImplementedError


class RegoConfigFlow(_CloudLogin, ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._found: list[Found] = []
        #: Sources ready to go into the entry, in priority order.
        self._sources: list[dict[str, Any]] = []
        #: EMS-ESP sources still to ask a login for.
        self._pending_auth: list[dict[str, Any]] = []
        self._title: str | None = None
        self._scan_task = None
        self._cloud: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return RegoOptionsFlow()

    # -- start --------------------------------------------------------------

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["search", "manual", "cloud"])

    async def async_step_search(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self._scan_task is None:
            self._scan_task = self.hass.async_create_task(async_find(self.hass))
        if not self._scan_task.done():
            return self.async_show_progress(step_id="search", progress_action="searching", progress_task=self._scan_task)
        try:
            found = self._scan_task.result()
        except Exception:
            _LOGGER.exception("The search failed")
            found = []
        self._scan_task = None
        self._found = [f for f in found if not _configured(self.hass, f.kind, host=f.host)]
        return self.async_show_progress_done(next_step_id="found" if self._found else "nothing_found")

    async def async_step_nothing_found(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="nothing_found", menu_options=["cloud", "manual", "search"])

    async def async_step_found(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """What the search found, one of each kind ticked: untick what is not this pump."""
        if user_input is not None:
            chosen = set(user_input.get("use") or [])
            picked = [f for f in self._found if f"{f.kind}@{f.host}" in chosen]
            if not picked:
                return await self.async_step_nothing_found()
            for found in picked:
                self._add_source({CONF_KIND: found.kind, CONF_HOST: found.host, **found.details.get("conf", {})}, found)
            return await self._async_next()
        options = [selector.SelectOptionDict(value=f"{f.kind}@{f.host}", label=f.label) for f in self._found]
        default, kinds = [], set()
        for f in self._found:
            if f.kind not in kinds:
                default.append(f"{f.kind}@{f.host}")
                kinds.add(f.kind)
        return self.async_show_form(
            step_id="found",
            data_schema=vol.Schema(
                {
                    vol.Required("use", default=default): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, multiple=True, mode=selector.SelectSelectorMode.LIST)
                    )
                }
            ),
            description_placeholders={"count": str(len(self._found))},
        )

    def _add_source(self, conf: dict[str, Any], found: Found | None = None) -> None:
        if any(s[CONF_KIND] == conf[CONF_KIND] for s in self._sources):
            return
        if found is not None and found.unique_id:
            conf.setdefault("unique_id", found.unique_id)
        self._sources.append(conf)
        self._sources.sort(key=lambda s: SOURCE_PRIORITY.index(s[CONF_KIND]))
        if conf[CONF_KIND] == SOURCE_EMSESP and CONF_TOKEN not in conf:
            self._pending_auth.append(conf)
        if found is not None and not self._title:
            brand = (found.details.get("brand") or "").strip()
            if brand:
                self._title = f"{brand} värmepump" if self.hass.config.language.startswith("sv") else f"{brand} heat pump"

    async def _async_next(self) -> ConfigFlowResult:
        """Logins still owed, then the cloud offer, then the entry."""
        if self._pending_auth:
            return await self.async_step_emsesp_auth()
        if not any(s[CONF_KIND] == SOURCE_CLOUD for s in self._sources):
            return await self.async_step_offer_cloud()
        return await self._async_create()

    # -- typed in --------------------------------------------------------------

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """An address: whatever answers there, EMS-ESP or Husdata."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            found = await async_identify(self.hass, host)
            if found is None:
                errors["base"] = "cannot_connect"
            elif _configured(self.hass, found.kind, host=found.host):
                return self.async_abort(reason="already_configured")
            else:
                self._add_source({CONF_KIND: found.kind, CONF_HOST: found.host, **found.details.get("conf", {})}, found)
                return await self._async_next()
        return self.async_show_form(
            step_id="manual", data_schema=vol.Schema({vol.Required(CONF_HOST, default="ems-esp.local"): str}), errors=errors
        )

    # -- EMS-ESP login --------------------------------------------------------

    async def async_step_emsesp_auth(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The web interface login, for writing. Empty leaves the gateway read only."""
        conf = self._pending_auth[0]
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                conf.update(
                    await _emsesp_token(
                        self.hass,
                        conf[CONF_HOST],
                        (user_input.get(CONF_USERNAME) or "").strip(),
                        user_input.get(CONF_PASSWORD) or "",
                        (user_input.get(CONF_TOKEN) or "").strip(),
                    )
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except SourceError:
                errors["base"] = "cannot_connect"
            else:
                self._pending_auth.pop(0)
                return await self._async_next()
        return self.async_show_form(
            step_id="emsesp_auth",
            data_schema=vol.Schema(
                {vol.Optional(CONF_USERNAME): str, vol.Optional(CONF_PASSWORD): PASSWORD, vol.Optional(CONF_TOKEN): str}
            ),
            errors=errors,
            description_placeholders={"host": conf[CONF_HOST]},
        )

    # -- announced on the network -------------------------------------------

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        return await self._async_discovered(str(discovery_info.host))

    async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> ConfigFlowResult:
        return await self._async_discovered(discovery_info.ip)

    async def _async_discovered(self, host: str) -> ConfigFlowResult:
        found = await async_identify(self.hass, host)
        if found is None:
            return self.async_abort(reason="not_supported")
        if _configured(self.hass, found.kind, host=found.host):
            return self.async_abort(reason="already_configured")
        if found.unique_id:
            await self.async_set_unique_id(found.unique_id)
            self._abort_if_unique_id_configured(updates=None)
        self._found = [found]
        self.context["title_placeholders"] = {"name": found.label}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        found = self._found[0]
        if user_input is not None:
            self._add_source({CONF_KIND: found.kind, CONF_HOST: found.host, **found.details.get("conf", {})}, found)
            return await self._async_next()
        return self.async_show_form(step_id="discovery_confirm", description_placeholders={"label": found.label})

    # -- the cloud ------------------------------------------------------------

    async def async_step_offer_cloud(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="offer_cloud", menu_options=["finish", "cloud"])

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._async_create()

    async def _async_cloud_chosen(self, conf: dict[str, Any]) -> ConfigFlowResult:
        self._add_source(conf)
        if not self._title:
            self._title = "Värmepump" if self.hass.config.language.startswith("sv") else "Heat pump"
        return await self._async_next()

    async def _async_create(self) -> ConfigFlowResult:
        if not self._sources:
            return self.async_abort(reason="no_sources")
        first = self._sources[0]
        unique = first.get("unique_id") or f"{first[CONF_KIND]}-{first.get(CONF_HOST) or first.get(CONF_DEVICE_ID)}"
        if self.unique_id is None:
            # A flow the user started goes ahead of one Home Assistant started
            # on its own for the same gateway (zeroconf/DHCP): creating the
            # entry ends that one.
            await self.async_set_unique_id(unique, raise_on_progress=False)
            self._abort_if_unique_id_configured()
        title = self._title or ("Värmepump" if self.hass.config.language.startswith("sv") else "Heat pump")
        return self.async_create_entry(title=title, data={CONF_SOURCES: self._sources})


class RegoOptionsFlow(_CloudLogin, OptionsFlow):
    """Poll intervals, the heating mode, and the sources: add one, log in, remove one."""

    def __init__(self) -> None:
        self._cloud: dict[str, Any] | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init", menu_options=["settings", "add_local", "cloud", "emsesp_login", "remove_source"]
        )

    def _sources(self) -> list[dict[str, Any]]:
        return [dict(s) for s in self.config_entry.data.get(CONF_SOURCES, [])]

    def _save_sources(self, sources: list[dict[str, Any]]) -> ConfigFlowResult:
        sources.sort(key=lambda s: SOURCE_PRIORITY.index(s[CONF_KIND]))
        self.hass.config_entries.async_update_entry(self.config_entry, data={**self.config_entry.data, CONF_SOURCES: sources})
        # Saving the options reloads the entry, which picks the sources up.
        return self.async_create_entry(data=dict(self.config_entry.options))

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = self.config_entry.options
        if user_input is not None:
            return self.async_create_entry(data={**options, **user_input})
        coordinator = getattr(self.config_entry, "runtime_data", None)
        circuits = [c for c in CIRCUITS if coordinator is not None and coordinator.writable_role(f"{c}_room_setpoint")]
        step = selector.NumberSelector(
            selector.NumberSelectorConfig(min=-6, max=4, step=0.5, unit_of_measurement="°C", mode=selector.NumberSelectorMode.BOX)
        )
        schema: dict = {
            vol.Required(CONF_SCAN_INTERVAL, default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)
            ),
            vol.Required(
                CONF_CLOUD_SCAN_INTERVAL, default=options.get(CONF_CLOUD_SCAN_INTERVAL, DEFAULT_CLOUD_SCAN_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
            vol.Required(CONF_STEP_BLOCKED, default=options.get(CONF_STEP_BLOCKED, DEFAULT_STEPS["blocked"])): step,
            vol.Required(CONF_STEP_ECO, default=options.get(CONF_STEP_ECO, DEFAULT_STEPS["eco"])): step,
            vol.Required(CONF_STEP_BOOST, default=options.get(CONF_STEP_BOOST, DEFAULT_STEPS["boost"])): step,
        }
        if circuits:
            schema[vol.Required(CONF_MODE_CIRCUITS, default=options.get(CONF_MODE_CIRCUITS, circuits))] = (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(options=circuits, multiple=True, mode=selector.SelectSelectorMode.LIST)
                )
            )
        return self.async_show_form(step_id="settings", data_schema=vol.Schema(schema))

    async def async_step_add_local(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            found = await async_identify(self.hass, user_input[CONF_HOST].strip())
            sources = self._sources()
            if found is None:
                errors["base"] = "cannot_connect"
            elif _configured(self.hass, found.kind, host=found.host):
                return self.async_abort(reason="already_configured")
            elif any(s[CONF_KIND] == found.kind for s in sources):
                errors["base"] = "kind_present"
            else:
                sources.append({CONF_KIND: found.kind, CONF_HOST: found.host, **found.details.get("conf", {})})
                return self._save_sources(sources)
        return self.async_show_form(
            step_id="add_local", data_schema=vol.Schema({vol.Required(CONF_HOST): str}), errors=errors
        )

    async def async_step_emsesp_login(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        sources = self._sources()
        conf = next((s for s in sources if s[CONF_KIND] == SOURCE_EMSESP), None)
        if conf is None:
            return self.async_abort(reason="no_emsesp")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                login = await _emsesp_token(
                    self.hass,
                    conf[CONF_HOST],
                    (user_input.get(CONF_USERNAME) or "").strip(),
                    user_input.get(CONF_PASSWORD) or "",
                    (user_input.get(CONF_TOKEN) or "").strip(),
                )
            except AuthError:
                errors["base"] = "invalid_auth"
            except SourceError:
                errors["base"] = "cannot_connect"
            else:
                for key in (CONF_TOKEN, CONF_USERNAME, CONF_PASSWORD):
                    conf.pop(key, None)
                conf.update(login)
                return self._save_sources(sources)
        return self.async_show_form(
            step_id="emsesp_login",
            data_schema=vol.Schema(
                {vol.Optional(CONF_USERNAME): str, vol.Optional(CONF_PASSWORD): PASSWORD, vol.Optional(CONF_TOKEN): str}
            ),
            errors=errors,
            description_placeholders={"host": conf[CONF_HOST]},
        )

    async def _async_cloud_chosen(self, conf: dict[str, Any]) -> ConfigFlowResult:
        sources = [s for s in self._sources() if s[CONF_KIND] != SOURCE_CLOUD]
        sources.append(conf)
        return self._save_sources(sources)

    async def async_step_remove_source(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        sources = self._sources()
        if user_input is not None:
            remove = set(user_input.get("remove") or [])
            keep = [s for s in sources if s[CONF_KIND] not in remove]
            if not keep:
                return self.async_abort(reason="last_source")
            return self._save_sources(keep)
        return self.async_show_form(
            step_id="remove_source",
            data_schema=vol.Schema(
                {
                    vol.Optional("remove", default=[]): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[s[CONF_KIND] for s in sources], multiple=True, mode=selector.SelectSelectorMode.LIST
                        )
                    )
                }
            ),
        )

