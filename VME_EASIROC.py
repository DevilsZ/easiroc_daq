from ConfigLoader import ConfigLoader
from RBCP import RBCP
import logging
import os
import time
import socket
import struct
import select
#from struct import pack

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class Easiroc:
    def __init__(self):
        self.slow_control = None
        self.probe = None
        self.read_register = None
        self.raz_chn = False
        self.val_evt = True
        self.reset_pa = True
        self.pwr_on = True
        self.select_sc = True
        self.load_sc = False
        self.rstb_sr = True
        self.rstb_read = True

class VmeEasiroc:
    def __init__(self, host, tcp_port, udp_port, yaml_dir):
        self.host = host
        self.tcp_port = tcp_port
        self.rbcp = RBCP(self.host, udp_port)
        self.yaml_dir = yaml_dir

        self.send_adc = False
        self.send_tdc = False
        self.send_scaler = False
        self.send_stp = False
        self.new_format = False
        self.reload_setting()
        self.exit_daq_mode()
        #self.send_adc = True
        #self.send_tdc = False
        #self.send_scaler = True
        #self.send_stp = True
        #self.new_format = True

    @property
    def easiroc1(self):
        return self._easiroc1

    @easiroc1.setter
    def easiroc1(self, value):
        self._easiroc1 = value

    @property
    def easiroc2(self):
        return self._easiroc2

    @easiroc2.setter
    def easiroc2(self, value):
        self._easiroc2 = value

    def send_direct_control(self):
        # KK address = self.direct_control_address()
        direct_control_register0 = [
            # MSB
            self.easiroc1.rstb_read,
            self.easiroc1.rstb_sr,
            self.easiroc1.load_sc,
            self.easiroc1.select_sc,
            self.easiroc1.pwr_on,
            self.easiroc1.reset_pa,
            self.easiroc1.val_evt,
            self.easiroc1.raz_chn,
            # LSB
        ]

        direct_control_register1 = [
            # MSB
            self.easiroc2.rstb_read,
            self.easiroc2.rstb_sr,
            self.easiroc2.load_sc,
            self.easiroc2.select_sc,
            self.easiroc2.pwr_on,
            self.easiroc2.reset_pa,
            self.easiroc2.val_evt,
            self.easiroc2.raz_chn,
            # LSB
        ]

        direct_control_register2 = [
            # MSB
            False,
            False,
            False,
            False,
            False,
            False,
            self.start_cycle2,
            self.start_cycle1,
            # LSB
        ]

        direct_control_register = [
            direct_control_register0,
            direct_control_register1,
            direct_control_register2
        ]

#        direct_control_register = [
 #           sum((1 << i) for i, j in enumerate(reg) if j) for reg in direct_control_register
  #      ]
        direct_control_register = [
            sum((1 << (len(reg) - 1 - i)) for i, j in enumerate(reg) if j) for reg in direct_control_register
        ]

        logger.debug("VmeEasiroc::sendDirectControl: {:08b} {:08b} {:08b}".format(
            direct_control_register[0],
            direct_control_register[1],
            direct_control_register[2]
        ))

        self.rbcp.write(self.direct_control_address(), direct_control_register)

    def send_slow_control(self):
        self.easiroc1.select_sc = True
        self.easiroc2.select_sc = True
        self.send_slow_control_sub(self.easiroc1.slow_control, self.easiroc2.slow_control)

    def send_probe_register(self):
        self.easiroc1.select_sc = False
        self.easiroc2.select_sc = False

        if all(i == 0 for i in self.easiroc1.probe):
            logger.debug('SelectProbe: EASIROC1 >> OFF')
        else:
            logger.debug('SelectProbe: EASIROC1 >> ON')

        if all(i == 0 for i in self.easiroc2.probe):
            logger.debug('SelectProbe: EASIROC2 >> OFF')
        else:
            logger.debug('SelectProbe: EASIROC2 >> ON')

        logger.debug('Send ProbeRegister')
        self.send_slow_control_sub(self.easiroc1.probe, self.easiroc2.probe)

    def reset_probe_register(self):
        self.easiroc1.select_sc = False
        self.easiroc2.select_sc = False

        logger.debug('Reset Probe Register')
        self.send_slow_control_sub([0] * 20, [0] * 20)

    def send_read_register(self):
        if self.easiroc1.read_register == -1:
            logger.debug('SelectHg : EASIROC1 >> OFF')
        else:
            logger.debug('SelectHg : EASIROC1 >> ON')

        if self.easiroc2.read_register == -1:
            logger.debug('SelectHg : EASIROC2 >> OFF')
        else:
            logger.debug('SelectHg : EASIROC2 >> ON')

        self.reset_read_register()

        if self.easiroc1.read_register >= 0:
            logger.debug(f"ReadRegister: {self.easiroc1.read_register}")
            address = self.read_register1_address()
            self.rbcp.write(address, self.easiroc1.read_register)

        if self.easiroc2.read_register >= 0:
            logger.debug(f"ReadRegister: {self.easiroc2.read_register}")
            address = self.read_register2_address()
            self.rbcp.write(address, self.easiroc2.read_register)

    def send_pedestal_suppression(self):
        address = self.pedestal_suppression_address()
        pedestal_suppression_value = self.config_loader.to_pedestal_suppression()['HG'] + self.config_loader.to_pedestal_suppression()['LG']
        logger.debug(f"PedestalSuppression: {pedestal_suppression_value}")
        self.rbcp.write16bit(address, pedestal_suppression_value)

    def reset_read_register(self):
        self.easiroc1.rstb_read = False
        self.easiroc2.rstb_read = False
        self.send_direct_control()

        self.easiroc1.rstb_read = True
        self.easiroc2.rstb_read = True
        self.send_direct_control()
        
    def send_selectable_logic(self):
        address = self.selectable_logic_address()

        selectable_logic = self.config_loader.to_selectable_logic()
        logger.debug(f"SelectableLogic: {selectable_logic}")
        self.rbcp.write(address, selectable_logic)

    def send_trigger_pla(self):
        address = self.trigger_pla_address()

        trigger_pla_value = self.config_loader.to_trigger_pla()
        logger.debug(f"TriggerPla: {trigger_pla_value}")
        self.rbcp.write(address, trigger_pla_value['Cmd'])
        self.rbcp.write(address + 1, trigger_pla_value['Channel'])
        self.rbcp.write(address + 2, trigger_pla_value['C_moni1'])
        self.rbcp.write(address + 3, trigger_pla_value['C_moni2'])
        self.rbcp.write32bit(address + 4, trigger_pla_value['AndLogicCh1x'])
        self.rbcp.write32bit(address + 68, trigger_pla_value['AndLogicCh2x'])
        self.rbcp.write32bit(address + 132, trigger_pla_value['OrLogicCh1x'][0])
        self.rbcp.write32bit(address + 140, trigger_pla_value['OrLogicCh1x'][1])
        self.rbcp.write32bit(address + 148, trigger_pla_value['OrLogicCh1x'][2])
        self.rbcp.write32bit(address + 156, trigger_pla_value['OrLogicCh1x'][3])
        self.rbcp.write32bit(address + 136, trigger_pla_value['OrLogicCh2x'][0])
        self.rbcp.write32bit(address + 144, trigger_pla_value['OrLogicCh2x'][1])
        self.rbcp.write32bit(address + 152, trigger_pla_value['OrLogicCh2x'][2])
        self.rbcp.write32bit(address + 160, trigger_pla_value['OrLogicCh2x'][3])

    def send_trigger_width(self):
        address = self.trigger_width_address()

        trigger_width = self.config_loader.to_trigger_width()
        logger.debug(f"TriggerWidth: {trigger_width}")
        self.rbcp.write(address, trigger_width)

    def send_time_window(self):
        address = self.time_window_address()
        time_window = self.config_loader.to_time_window()
        logger.info(f"TimeWIndow: {time_window}")
        self.rbcp.write16bit(address, time_window)
        
    def send_trigger_values(self):
        address = self.trigger_values_address()

        trigger_mode = self.config_loader.to_trigger_mode()
        logger.debug(f"TriggerMode: {trigger_mode}")
        self.rbcp.write(address, trigger_mode)

        trigger_delay = self.config_loader.to_trigger_delay()
        logger.debug(f"TriggerDelay: {trigger_delay}")
        self.rbcp.write(address + 1, trigger_delay)

    def send_trigger_mode(self, ivalue):
        address = self.trigger_values_address()
        logger.debug(f"TriggerMode: {ivalue}")
        self.rbcp.write(address, ivalue)

    def send_trigger_delay(self, ivalue):
        address = self.trigger_values_address() + 1
        logger.debug(f"TriggerDelay: {ivalue}")
        self.rbcp.write(address, ivalue)

    def easiroc1_slow_control(self):
        return self.easiroc1.slow_control

    def easiroc2_slow_control(self):
        return self.easiroc2.slow_control

    def get_easiroc1_slow_control(self):
        return self.config_loader.get_easiroc1_slow_control()

    def get_easiroc2_slow_control(self):
        return self.config_loader.get_easiroc2_slow_control()

    def set_easiroc1_slow_control(self, key, value):
        self.config_loader.set_easiroc1_slow_control(key, value)
        self.easiroc1.slow_control = self.config_loader.to_easiroc1_slow_control()

    def set_easiroc2_slow_control(self, key, value):
        self.config_loader.set_easiroc2_slow_control(key, value)
        self.easiroc2.slow_control = self.config_loader.to_easiroc2_slow_control()

    def reload_setting(self):
        """Reload settings and initialize EASIROC configurations."""
        # Initialize ConfigLoader
        self.config_loader = ConfigLoader(
            os.path.abspath(os.path.join(os.path.dirname(__file__), 'yaml_common/RegisterAttribute.yml')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), 'yaml_common/RegisterValueAlias.yml')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), 'yaml_common/DefaultRegisterValue.yml')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), f'{self.yaml_dir}/RegisterValue.yml')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), 'yaml_common/InputDAC.yml')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), 'yaml_common/PedestalSuppression.yml')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), f'{self.yaml_dir}/TriggerPLA.yml')),
            os.path.abspath(os.path.join(os.path.dirname(__file__), 'yaml_common/Calibration.yml'))
        )

        # Initialize EASIROC1
        print("Initializing easiroc1")
        self.easiroc1 = Easiroc()
        self.easiroc1.slow_control = self.config_loader.to_easiroc1_slow_control()
        self.easiroc1.probe = self.config_loader.to_probe1_slow_control()
        self.easiroc1.read_register = self.config_loader.to_read_register1()
        self.easiroc1.raz_chn = False
        self.easiroc1.val_evt = True
        self.easiroc1.reset_pa = True
        self.easiroc1.pwr_on = True
        self.easiroc1.select_sc = True
        self.easiroc1.load_sc = False
        self.easiroc1.rstb_sr = True
        self.easiroc1.rstb_read = True

        # Initialize EASIROC2
        print("Initializing easiroc2")
        self.easiroc2 = Easiroc()
        self.easiroc2.slow_control = self.config_loader.to_easiroc2_slow_control()
        self.easiroc2.probe = self.config_loader.to_probe2_slow_control()
        self.easiroc2.read_register = self.config_loader.to_read_register2()
        self.easiroc2.raz_chn = False
        self.easiroc2.val_evt = True
        self.easiroc2.reset_pa = True
        self.easiroc2.pwr_on = True
        self.easiroc2.select_sc = True
        self.easiroc2.load_sc = False
        self.easiroc2.rstb_sr = True
        self.easiroc2.rstb_read = True

        # Initialize cycle flags
        self.start_cycle1 = False
        self.start_cycle2 = False

        # Additional settings (commented out in the original Ruby code)
        # self.select_hg = False
        # self.select_probe1 = False
        # self.select_probe2 = False
        # self.led_ready = False
        # self.led_busy = False
        # self.led_user_output = False
        # self.user_output = False

        # DAQ mode flag
        self.daq_mode = False

        # User clock output
        self.usr_clk_out = self.config_loader.to_usr_clk_out_register()

    def summary(self):
        return self.config_loader.summary()

    def version(self):
        address = self.version_address
        combined_data = self.rbcp.read(address, 6)

        version = combined_data[0:2]
        version_major = version[0] >> 4
        version_minor = version[0] & 0x0F
        version_hotfix = version[1] >> 4
        version_patch = version[1] & 0x0F

        def decode(data):
            unpacked = [byte for byte in data]  # Unpack bytes into integers
            decoded = [((value >> 4), (value & 0x0F)) for value in unpacked]
            flattened = [digit for pair in decoded for digit in pair]
            return int("".join(map(str, flattened)))

        year = decode(combined_data[2:4])
        month = decode([combined_data[4]])
        day = decode([combined_data[5]])

        return version_major, version_minor, version_hotfix, version_patch, year, month, day

    def read_event(self, number_to_read):
        print(f'  DEBUG: read_event {number_to_read} {self.host}')
        try:
            self.sock = socket.create_connection((self.host, self.tcp_port), timeout=None) # Timeout
            print(f'  DEBUG: Successfully connected to {self.host}:{self.tcp_port}')
            try:
                #print(f'  DEBUG: read_event (2) {self.host}')
                self.read_and_throw_previous_data()
                #print(f'  DEBUG: read_event (3) {self.host}')
                with self.enter_daq_mode():
                    for _ in range(number_to_read):
                        #print(f'  DEBUG: read_event (4) {self.host}')
                        header = self.receive_header()
                        #print(f"  DEBUG: data_size = {header['data_size']}")
                        data = self.receive_data(header['data_size'])
                        #print(f'  DEBUG: data = {header} {len(data)}')
                        yield header, data
                self.read_and_throw_previous_data()
            finally:
                self.sock.close()
        except (socket.timeout, ConnectionRefusedError) as e:
            print(f"  DEBUG: Connection failed: {e}")
            self.sock = None  # Disable socket as None
        except socket.error as e:
            print(f"  DEBUG: Socket error occurred: {e}")
            self.sock = None  # Disable socket as None

    def send_madc_control(self):
        address = self.monitor_adc_address()
        # Set ADC rate to 50Hz
        self.rbcp.write(address, 248)
        time.sleep(0.01)
        self.rbcp.write(address + 1, 0)

    def send_shutdown_hv(self):
        address = self.hv_control_address()
        # Send shutdown signal
        self.rbcp.write(address + 3, 0)

    def send_hv_control(self, value):
        address = self.hv_control_address()
        hv_const = self.config_loader.to_hv_control()
        if value < 0.00:
            print("Input value must be positive!")
            return
        if value > 90.00:
            print("Too large input value! Must be smaller than 90.00")
            return

        hv_dac = int(value * hv_const[0] + hv_const[1])
        print(f"MPPC bias voltage: {value:.2f}V, DAC bit: {hv_dac}")

        higher_8bit = hv_dac // 256
        lower_8bit = hv_dac % 256

        self.rbcp.write(address, higher_8bit)    # Set higher 8 bits to FPGA reg
        self.rbcp.write(address + 1, lower_8bit) # Set lower 8 bits to FPGA reg
        self.rbcp.write(address + 2, 1)          # Start DAC control

    def read_madc(self, data):
        address = self.monitor_adc_address()
        address2 = self.read_madc_address()
        madc_const = self.config_loader.to_madc_calibration()

        # Set MADC channel to FPGA register
        self.rbcp.write(address, data)
        time.sleep(0.01)  # wait for ADC channel change (default 0.2)
        self.rbcp.write(address + 1, 1)

        # Start to read MADC
        self.rbcp.write(address, 240)
        time.sleep(0.05)
        self.rbcp.write(address + 1, 0)

        # Read data
        time.sleep(0.01)  # wait for MADC data (default 1)
        higher_8bit = self.rbcp.read(address2, 1)
        lower_8bit = self.rbcp.read(address2 + 1, 1)

        dac1 = float(higher_8bit[0])
        dac2 = float(lower_8bit[0])
        read_dac = dac1 * 256 + dac2
        print(f"readDAC={read_dac}")

        if data == 3:
            read_madc = madc_const["HV"] * read_dac + madc_const["HVOffset"]
        elif data == 4:
            read_madc = madc_const["Current"] * read_dac
        elif data in [5, 0]:
            read_madc = madc_const["Temperature"] * read_dac / 65535 / 2.4 - 273
        elif data in [1, 2]:
            read_madc = madc_const["InputDac"] * read_dac
        else:
            read_madc = None  # default case if data doesn't match expected values

        return read_madc

    def set_ch(self, num):
        if num > 31:
            print("Channel number should be 0~31.")
            return

        address = self.monitor_adc_address()
        mux = 0

        if num < 16:
            if num % 2 == 0:
                mux = 199 - num // 2
            else:
                mux = 207 - num // 2
        elif num < 32:
            if num % 2 == 0:
                mux = 55 - (num - 16) // 2
            else:
                mux = 63 - (num - 16) // 2
        elif num == 32:
            mux = 0
        
        self.rbcp.write(address + 2, mux)
        time.sleep(0.01)  # default 0.2
    
    def send_usr_clk_out_register(self):
        address = self.usr_clk_out_address()
        self.rbcp.write(address, self.usr_clk_out)

    def send_stp_mode_register(self, ivalue):
        address = self.stp_mode_address()
        self.rbcp.write(address, ivalue)

    def send_test_pin_register(self, ivalue):
        address = self.test_pin_address()
        print(hex(address))
        print(hex(ivalue))
        self.rbcp.write(address, ivalue)
        time.sleep(0.01)

    def send_test_charge_register(self, ivalue):
        address = self.test_charge_address()
        print(hex(address))
        print(hex(ivalue))
        self.rbcp.write(address, ivalue)
        time.sleep(0.01)

    @staticmethod
    def direct_control_address():
        return 0x00000000

    @staticmethod
    def slow_control1_address():
        return 0x00000003

    @staticmethod
    def read_register1_address():
        return 0x0000003C

    @staticmethod
    def slow_control2_address():
        return 0x0000003D

    @staticmethod
    def read_register2_address():
        return 0x00000076

    @staticmethod
    def status_register_address():
        return 0x00000077

    @staticmethod
    def selectable_logic_address():
        return 0x00000078

    @staticmethod
    def trigger_width_address():
        return 0x00000088

    @staticmethod
    def time_window_address():
        return 0x00000100

    @staticmethod
    def pedestal_suppression_address():
        return 0x00001000

    @staticmethod
    def hv_control_address():
        return 0x00010000

    @staticmethod
    def monitor_adc_address():
        return 0x00010010

    @staticmethod
    def read_madc_address():
        return 0x00010020

    @staticmethod
    def usr_clk_out_address():
        return 0x00010030

    @staticmethod
    def stp_mode_address():
        return 0x00010034

    @staticmethod
    def test_pin_address():
        return 0x00010040

    @staticmethod
    def test_charge_address():
        return 0x00010044

    @staticmethod
    def trigger_values_address():
        return 0x00010100

    @staticmethod
    def trigger_pla_address():
        return 0x00010200

    @staticmethod
    def version_address():
        return 0xF0000000

    @staticmethod
    def daq_mode_bit():
        return 0x01

    @staticmethod
    def send_adc_bit():
        return 0x02

    @staticmethod
    def send_tdc_bit():
        return 0x04

    @staticmethod
    def send_scaler_bit():
        return 0x08

    @staticmethod
    def send_stp_bit():
        return 0x10

    @staticmethod
    def new_format_bit():
        return 0x80

    def send_slow_control_sub(self, easiroc1, easiroc2):
        self.easiroc1.load_sc = False
        self.easiroc1.rstb_sr = True
        self.easiroc2.load_sc = False
        self.easiroc2.rstb_sr = True
        self.start_cycle1 = False
        self.start_cycle2 = False
        self.send_direct_control()

        print("easiroc1 (int list):", list(easiroc1))
        print("hex     :", [f"{b:02X}" for b in easiroc1])
        
        logger.debug("VmeEasiroc::sendSlowControl:")
        logger.debug("Easiroc1")
        logger.debug("".join(f"{i:02X}, " for i in easiroc1))
        address = self.slow_control1_address()
        self.rbcp.write(address, easiroc1)

        logger.debug("VmeEasiroc::sendSlowControl:")
        logger.debug("Easiroc2")
        logger.debug("".join(f"{i:02X}, " for i in easiroc2))
        address = self.slow_control2_address()
        self.rbcp.write(address, easiroc2)

        self.start_cycle1 = True
        self.start_cycle2 = True
        self.send_direct_control()

        time.sleep(0.1)

        self.easiroc1.load_sc = True
        self.easiroc2.load_sc = True
        self.start_cycle1 = False
        self.start_cycle2 = False
        self.send_direct_control()

        self.easiroc1.load_sc = False
        self.easiroc2.load_sc = False
        self.send_direct_control()

    def write_status_register(self, data=0):
        address = self.status_register_address()
        if self.daq_mode:
            data |= self.daq_mode_bit()
        if self.send_adc:
            data |= self.send_adc_bit()
        if self.send_tdc:
            data |= self.send_tdc_bit()
        if self.send_scaler:
            data |= self.send_scaler_bit()
        if self.send_stp:
            data |= self.send_stp_bit()
        if self.new_format:
            data |= self.new_format_bit()
        logger.debug(f"write status register {data}")
        self.rbcp.write(address, data)

    def enter_daq_mode(self):
        logger.info("enter DAQ MODE")
        self.daq_mode = True
        self.write_status_register()
        # Python context management
        class DAQContext:
            def __init__(self, outer):
                self.outer = outer

            def __enter__(self):
                return self.outer

            def __exit__(self, exc_type, exc_value, traceback):
                self.outer.exit_daq_mode()

        return DAQContext(self)

    def exit_daq_mode(self):
        logger.info("exit DAQ MODE")
        self.daq_mode = False
        self.write_status_register()
        print('EXIT complete')

    def decode_word(self, word):
        if self.new_format:
            normal_frame = 0xC0000000
            frame = word & 0xC0000000
            if frame != normal_frame:
                raise ValueError("Frame Error 1")

            return word
        else:
            normal_frame = 0x80000000
            frame = word & 0x80808080
            if frame != normal_frame:
                raise ValueError("Frame Error 2")

            ret = ((word & 0x7F000000) >> 3) | ((word & 0x007F0000) >> 2) | \
                  ((word & 0x00007F00) >> 1) | ((word & 0x0000007F) >> 0)
            return ret

    def receive_n_byte(self, num_bytes):
        #print(f'  DEBUG: receive_n_byte (0) {self.host}')
        data = b''
        received_bytes = 0
        self.sock.settimeout(None) # Never time out
        while received_bytes < num_bytes:
            #print(f'  DEBUG: receive_n_byte (1) {self.host} {num_bytes} - {received_bytes}')
            try:
                chunk = self.sock.recv(num_bytes - received_bytes)
                if not chunk:
                    raise ConnectionError("Connection closed before receiving all data")
                #data += chunk
                received_data = chunk
            except socket.timeout:
                print("Receiving data timed out")
                raise
            except socket.error as e:
                print(f"Socket error: {e}")
                raise

            #print(f'  DEBUG: receive_n_byte (2) {self.host}')
            if not received_data:
                raise ConnectionError("Socket connection closed unexpectedly.")
            #print(f'  DEBUG: receive_n_byte (3) {self.host}')
            data += received_data
            received_bytes += len(received_data)
        return data

    def receive_header(self):
        #print(f'  DEBUG: receive_header (0) {self.host}')
        raw_header = self.receive_n_byte(4)
        header = self.decode_word(struct.unpack(">I", raw_header)[0])  # Big-endian unsigned int
        #print(f'  DEBUG: receive_header (1) {self.host}')
        if self.new_format:
            #print(f'  DEBUG: receive_header (2.1) {self.host}')
            if (header & 0xFFFF0000) == 0xFF7C0000:
                is_header = 1
            else:
                is_header = 0
        else:
            #print(f'  DEBUG: receive_header (2.2) {self.host}')
            is_header = (header >> 27) & 1
            if is_header != 1:
                raise ValueError("Frame Error 3")
        
        data_size = header & 0x0FFF
        return {"data_size": data_size, "header": struct.pack(">I", header)}

    def receive_data(self, data_size):
        raw_data = self.receive_n_byte(4 * data_size)
        words = struct.unpack(f">{data_size}I", raw_data)  # Big-endian unsigned ints
        data = [self.decode_word(word) for word in words]
        if self.new_format:
            if not all((word >> 31) & 1 == 1 for word in data):
                raise ValueError("Frame Error 4")
        else:
            if not all((word >> 27) & 1 == 0 for word in data):
                raise ValueError("Frame Error 5")
        return data

    def read_and_throw_previous_data(self, timeout=0.1, max_total_bytes = 10000):
        # print(f'  DEBUG: read_and_throw_previous_data (0) {self.host} {timeout}')
        thrown_size = 0
        while True: # forever loop
            #print(f'  DEBUG: read_and_throw_previous_data (1) {self.host} {thrown_size}')
            ready, _, _ = select.select([self.sock], [], [], timeout)
            #print(ready)
            if not ready:
                break
            dummy = ready[0].recv(256) # receive up to 256 bytes
            # print(f'  DEBUG:: dummy = {dummy}')
            if len(dummy) == 0:
                print("Connection closed")
                break
            if not dummy:  # b'' means socket closed
                print(f'  DEBUG: socket closed by peer')
                break
            thrown_size += len(dummy)
            #if thrown_size > max_total_bytes:
            #    print("Too much data, stopping.")
            #    break
        return thrown_size

    @staticmethod
    def hg():
        return lambda i: ((i >> 21) & 1) == 0 and ((i >> 19) & 1) == 0

    @staticmethod
    def lg():
        return lambda i: ((i >> 21) & 1) == 0 and ((i >> 19) & 1) == 1

    @staticmethod
    def tdc():
        return lambda i: ((i >> 21) & 1) == 1
