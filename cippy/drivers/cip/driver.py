from contextlib import contextmanager
from functools import cached_property
from typing import Any, Self, cast
from collections.abc import Generator, Sequence
from cippy._logging import get_logger
from cippy.data_types import DataType
from cippy.protocols.cip import CIPConfig, CIPConnection, CIPRoute
from cippy.protocols.cip.cip_object import CIPAttribute, CIPObject
from cippy.protocols.cip.object_library.identity import Identity
from cippy.protocols.ethernetip import ETHERNETIP_PORT, EIPConfig, EIPConnection


class CIPDriver:
    __log = get_logger(__qualname__)

    def __init__(self, path: str | None = None, connection: CIPConnection | None = None) -> None:
        self._connection: CIPConnection
        match path, connection:
            case None, None:
                raise ValueError("must supply `path` or `connection`")
            case None, CIPConnection():
                self._connection = connection
            case str(), None:
                host, port, route = parse_connection_path(path)
                self._connection = CIPConnection(
                    config=CIPConfig(route), transport=EIPConnection(EIPConfig(host=host, port=port))
                )
            case _:
                raise ValueError("cannot supply both `path` and `connection`")

    @property
    def connection(self) -> CIPConnection:
        return self._connection

    def open(self, cip_connected: bool = False) -> Self:
        if not self._connection.connected:
            self._connection.connect()
        if cip_connected and not self._connection.cip_connected:
            try:
                self._connection.forward_open()
            except Exception:
                raise ConnectionError("failed to create cip connection")
        return self

    def close(self) -> None:
        if self._connection.cip_connected:
            try:
                self._connection.forward_close()
            except Exception:
                self.__log.exception("failed to close cip connection")
        if self._connection.connected:
            self._connection.disconnect()

    def __enter__(self):
        if not self.connection.connected:
            self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.close()
        except ConnectionError:
            self.__log.exception("error closing connection")
            return False
        else:
            if not exc_type:
                return True
            self.__log.exception("unhandled client error", exc_info=(exc_type, exc_val, exc_tb))
            return False

    @cached_property
    def identity(self) -> Identity | None:
        try:
            if not (resp := self.read_object(Identity)):
                self.__log.error(f"failed to get identity for {self.connection.connection_path}")
                return None
            return resp
        except Exception:
            self.__log.exception("failed to get identity")
            return None

    @contextmanager
    def temporary_route(
        self,
        route: CIPRoute | str,
        cip_connected: bool = False,
    ) -> Generator[Self, None, None]:
        try:
            self.__log.debug(f"Creating temporary driver with additional route {route!r}...")
            cfg = CIPConfig(
                route=self.connection.config.route / route,
                connected_config=self.connection.config.connected_config,
                unconnected_config=self.connection.config.unconnected_config,
            )
            conn = CIPConnection(transport=self.connection._transport, config=cfg)
            self.__log.debug(f"Temporary route config: {cfg}")
            with self.__class__(connection=conn).open(cip_connected=cip_connected) as driver:
                yield driver
        finally:
            self.__log.debug("... temporary route driver closed")

    def __str__(self):
        return f"{self.__class__.__name__} @ {self.connection.connection_path}"

    def read_object[T: CIPObject](
        self, cip_object: type[T], instance: int | None = CIPObject.Instance.DEFAULT
    ) -> T | None:
        """
        Attempts to read all attributes from an object, those defined in the `Get Attributes All` response.
        First tries to use the get attributes all service, if that fails, it will try the get attributes list service
        with all attributes, if that fails, it will try the get attribute single service for each attribute.
        If any succeed, a `cip_object` instance will be returned, else `None`. If one of the fallback services was used,
        any failed attributes will be set to `None` in the object instance.
        """
        self.__log.info(f"reading object {cip_object} ({instance=})...")

        try:
            if resp := self.connection.get_attributes_all(cip_object, instance):
                value = cip_object(instance=instance, **resp.data)  # type: ignore
                self.__log.info(f"... success: {value}")
                return value
            self.__log.info(f"...failed to read object {cip_object} with get_attributes_all: {resp.status_message}")
            try:
                _all_struct = cip_object.__class_struct__ if not instance else cip_object.__instance_struct__
                _attrs = cip_object.__cip_class_attributes__ if not instance else cip_object.__cip_instance_attributes__
                attrs = [_attrs[m] for m in _all_struct.__struct_members__]
            except KeyError as err:
                self.__log.error(f"...invalid get_attributes_all response type, cip object missing attribute: {err}")
                return None

            values = {}
            self.__log.info(f"...attempting to read object {cip_object} ({instance=}) with get_attribute_list...")
            if list_resp := self.connection.get_attribute_list(attrs, instance):
                for att in attrs:
                    attr_resp = getattr(list_resp.data, att.name)
                    values[att.name] = None if attr_resp.status else attr_resp.data
            else:
                self.__log.info("...get_attribute_list failed, trying get_attribute_single reads...")
                for att in attrs:
                    self.__log.info(f" ...reading {att.name!r}...")
                    if resp := self.connection.get_attribute_single(att, instance):
                        values[att.name] = resp.data
                        self.__log.info(f" ... success: {resp.data}")
                    else:
                        self.__log.info(f"... failed to read {att.name}: {resp.status_message}")
                        values[att.name] = None
            if any(failed_attrs := [k for k, v in values.items() if v is None]):
                self.__log.info(f"... failed to read attributes from object: {', '.join(failed_attrs)}")
                return None
            else:
                value = cast(T, cip_object(instance=instance, **values))
                self.__log.info(f"... success: {value}")
                return value
        except Exception:
            self.__log.exception(f"unhandled exception trying to read object {cip_object}")

    def read_attribute[T: DataType, TObj: CIPObject](
        self, attribute: CIPAttribute[T, TObj], instance: int | None = CIPObject.Instance.DEFAULT
    ) -> T | None:
        """
        Attempts to read an attribute. If successful, the value of that attribute will be returned, else None.
        """
        self.__log.info("reading attribute %s (instance=%d)...", attribute, instance)
        try:
            if resp := self.connection.get_attribute_single(attribute, instance):
                self.__log.info(f"... success: {resp.data}")
                return cast(T, resp.data)
            else:
                self.__log.info(f"... failed to read {attribute}: {resp.status_message}")
                return None
        except Exception:
            self.__log.exception(f"unhandled exception trying to read attribute {attribute} ({instance=})")
            return None

    def read_attributes[T: DataType, TObj: CIPObject](
        self, attributes: Sequence[CIPAttribute[Any, TObj]], instance: int | None = CIPObject.Instance.DEFAULT
    ) -> list[Any | None] | None:
        """
        Attempts to read attributes from an object, all attributes must be from the same object.
        First it will attempt using the get attributes list, if that fails it will attempt
        to use the get attribute single service for each attribute.
        If successful, a list of the attribute values will be returned. Individual attributes may fail
        while others are successful, failed attributes will be set to `None`, the length and order
        of the requested attributes will be maintained. Unless, if all attributes fail to read, the `None` is returned..
        """
        self.__log.info("reading attributes %s (instance=%d)...", ", ".join(str(a) for a in attributes), instance)
        try:
            if resp := self.connection.get_attribute_list(attributes, instance):
                self.__log.info(f"... success: {resp.data}")
                values: list[T | None] = [a.data if a else None for a in resp.data]  # type: ignore
            else:
                self.__log.info("... get_attribute_list failed, attempting get_attribute_single reads...")
                values = [self.read_attribute(a, instance) for a in attributes]
            if all(v is None for v in values):
                self.__log.info("... all attributes failed, returning None")
                return None
            else:
                self.__log.info(f"... success: {values}")
                return values

        except Exception:
            self.__log.exception(f"unhandled exception trying to read attribute {attributes} ({instance=})")
            return None


def parse_connection_path(path: str) -> tuple[str, int, CIPRoute]:
    try:
        _path = path.replace(",", "/").replace("\\", "/").split("/", maxsplit=1)
        _host, _route = (_path[0], _path[1]) if len(_path) == 2 else (_path[0], None)
        _host = _host.split(":", maxsplit=1)
        if len(_host) == 2:
            host, port = _host[0], int(_host[1])
        else:
            host, port = _host[0], ETHERNETIP_PORT

        return host, port, CIPRoute(_route)

    except Exception as err:
        raise ValueError("invalid connection path") from err
