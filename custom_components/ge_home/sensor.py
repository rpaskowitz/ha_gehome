"""GE Home Sensor Entities"""
import logging
from typing import Callable
import voluptuous as vol
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import entity_platform
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN, 
    SERVICE_SET_TIMER, 
    SERVICE_CLEAR_TIMER, 
    SERVICE_SET_INT_VALUE
)
from .entities import GeErdSensor
from .devices import ApplianceApi
from .update_coordinator import GeHomeUpdateCoordinator

ATTR_DURATION = "duration"
ATTR_VALUE = "value"

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable):
    """GE Home sensors."""
    _LOGGER.debug('Adding GE Home sensors')
    coordinator: GeHomeUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    registry = er.async_get(hass)
    _LOGGER.debug(f'Coordinator initialized: {coordinator.initialized}')

    # Get the platform
    platform = entity_platform.async_get_current_platform()

    @callback
    def async_devices_discovered(apis: list[ApplianceApi]):
        _LOGGER.debug(f'Found {len(apis):d} appliance APIs')
        for api in apis:
            _LOGGER.debug(f'API {api.mac_addr}: Has {len(api.entities)} total entities')
            sensor_entities = [e for e in api.entities if isinstance(e, GeErdSensor)]
            _LOGGER.debug(f'API {api.mac_addr}: Has {len(sensor_entities)} sensor entities')
            for entity in sensor_entities:
                _LOGGER.debug(f'API {api.mac_addr}: Sensor entity {entity.unique_id} - registered: {registry.async_is_registered(entity.entity_id)}')
        
        entities = [
            entity
            for api in apis
            for entity in api.entities
            if isinstance(entity, GeErdSensor)
            if not registry.async_is_registered(entity.entity_id)
        ]
        _LOGGER.debug(f'Found {len(entities):d} unregistered sensors')
        async_add_entities(entities)

    #if we're already initialized at this point, call device
    #discovery directly, otherwise add a callback based on the
    #ready signal
    if coordinator.initialized:
        _LOGGER.debug('Coordinator already initialized, calling device discovery directly')
        async_devices_discovered(coordinator.appliance_apis.values())
    else:
        _LOGGER.debug('Coordinator not ready, registering callback for ready signal')
        # add the ready signal and register the remove callback
        coordinator.add_signal_remove_callback(
            async_dispatcher_connect(hass, coordinator.signal_ready, async_devices_discovered))
    
    # register set_timer entity service
    platform.async_register_entity_service(
    SERVICE_SET_TIMER,
    {
        vol.Required(ATTR_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=360)
        )
    },
    set_timer)

    # register clear_timer entity service
    platform.async_register_entity_service(SERVICE_CLEAR_TIMER, {}, 'clear_timer')

    # register set_value entity service
    platform.async_register_entity_service(
    SERVICE_SET_INT_VALUE,
    {
        vol.Required(ATTR_VALUE): vol.All(
            vol.Coerce(int), vol.Range(min=0)
        )
    },
    set_int_value)    

async def set_timer(entity, service_call):
    ts = timedelta(minutes=int(service_call.data['duration']))
    await entity.set_timer(ts)

async def set_int_value(entity, service_call):
    await entity.set_value(int(service_call.data['value']))