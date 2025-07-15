from cippy.util import PredefinedValues


class DeviceTypes(PredefinedValues):
    generic_device = 0x00
    ac_drive = 0x02
    motor_overload = 0x03
    limit_switch = 0x04
    proximity_switch = 0x05
    photoelectric_sensor = 0x06
    discrete_io = 0x07
    resolver = 0x09
    communications_adapter = 0x0C
    plc = 0x0E
    position_controller = 0x10
    dc_drive = 0x13
    contactor = 0x15
    motor_starter = 0x16
    soft_start = 0x17
    human_machine_interface = 0x18
    mass_flow_controller = 0x1A
    pneumatic_valve = 0x1B
    vacuum_pressure_gauge = 0x1C
    process_control_value = 0x1D
    residual_gas_analyzer = 0x1E
    dc_power_generator = 0x1F
    rf_power_generator = 0x20
    turbomolecular_vacuum_pump = 0x21
    encoder = 0x22
    safety_discrete_io = 0x23
    fluid_flow_controller = 0x24
    cip_motion_driver = 0x25
    compoNet_repeater = 0x26
    enhanced_mass_flow_controller = 0x27
    cip_modbus_device = 0x28
    cip_modbus_translator = 0x29
    safety_analog_io = 0x2A
    generic_device_keyable = 0x2B
    managed_switch = 0x2C
    cip_motion_safety_drive = 0x2D
    safety_drive = 0x2E
    cip_motion_encoder = 0x2F
    cip_motion_io = 0x31
    controlnet_physical_layer_component = 0x32
    embedded_component = 0xC8
