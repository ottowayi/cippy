from cippy._logging import get_logger
from cippy.const import DeviceTypes
from cippy.data_types import PortIdentifier
from cippy.drivers import CIPDriver
from cippy.exceptions import DriverError
from cippy.protocols.cip import CIPConnection


class LogixDriver(CIPDriver):
    __log = get_logger(__qualname__)

    def __init__(
        self, path: str | None = None, auto_slot: bool = True, connection: CIPConnection | None = None
    ) -> None:
        if path is not None and auto_slot:
            path = self._find_plc_slot(path)

        super().__init__(path, connection)

    def _find_plc_slot(self, path: str) -> str:
        try:
            self.__log.info(f"locating plc for device: {path}")
            with CIPDriver(path) as driver:
                if driver.identity and driver.identity.device_type == DeviceTypes.plc:
                    self.__log.info(f"device is a plc: {driver.identity}")
                    return path
                for i in range(17):  # probably a reasonable max chassis size
                    try:
                        self.__log.info(f"checking slot {i}...")
                        with driver.temporary_route(driver.connection.route / (PortIdentifier.backplane, i)) as _driver:
                            if _driver.identity is None:
                                self.__log.info(f"... failed to get identity of slot {i}")
                                continue
                            if _driver.identity.device_type == DeviceTypes.plc:  # type: ignore - any exception is ok
                                self.__log.info(f"... found plc: {_driver.identity}")
                                return f"{path}/{PortIdentifier.backplane}/{i}"
                            else:
                                self.__log.info(f"... not a plc: {driver.identity}")
                    except Exception as err:
                        self.__log.exception(f"exception checking slot {i}")
                        self.__log.info(f"... error checking slot {i}: {err}")

            self.__log.error(f"failed to locate plc for device: {path}")
            raise DriverError(f"failed to locate plc for device: {path}")

        except DriverError:
            raise
        except Exception as err:
            raise DriverError(f"error locating plc for device: {path}") from err
