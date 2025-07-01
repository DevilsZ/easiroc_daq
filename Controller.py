import sys
import os
import logging
import signal
import readline
import time
import subprocess
import yaml
import optparse

from queue import Queue
from datetime import datetime
from tqdm import tqdm

from VME_EASIROC import VmeEasiroc
# Set environment variable equivalent to ENV['INLINEDIR']
os.environ['INLINEDIR'] = os.path.dirname(os.path.abspath(__file__))

class CommandDispatcher:
    COMMANDS = [
        'shutdownHV', 'setHV', 'statusHV', 'statusTemp', 'statusInputDAC', 
        'checkHV', 'setInputDAC', 'setRegister', 'setThreshold', 
        'increaseHV', 'decreaseHV', 'initialCheck', 'muxControl', 'slowcontrol', 
        'standby', 'fit', 'drawScaler', 'dsleep', 'read', 'adc', 'tdc', 'scaler', 'stp',
        'regacyDataFormat', 'reset', 'help', 'version', 
        'timeStamp', 'exit', 'quit', 'progress', 'stop', 'makeError', 'setStpMode', 
        'setTESTPIN', 'setTestCharge', 'setTriggerMode', 'setTriggerDelay', 
        'show_easiroc1', 'show_easiroc2', 'slowcontrol_only', 'testChargeTo', 'dummy_read'
    ]

    def __init__(self, vme_easiroc, q):
        self.vme_easiroc = vme_easiroc
        self.q = q
        self.stop_requested = False
        
    def dispatch(self, line):
        if not line.strip():
            print('Empty command: Please input command in the text field')
            return
        
        parts = line.split()
        command = parts[0]
        args = parts[1:]

        if command not in self.COMMANDS:
            print(f"unknown command {command}")
            return
        elif command in ['progress', 'stop']:
            print(f"command {command} works only while reading out data ... ")
            return
        
        try:
            getattr(self, command)(*args)
        except AttributeError:
            print(f"Command '{command}' not found.")
        except TypeError as e:
            print(f"{e} invalid argument '{' '.join(args)}' for command '{command}'")
        except Exception as e:
            print(str(e))
            print("exit...")
            self.setHV(0.0)
            time.sleep(1)
            sys.exit()

    def dsleep(self, time_val):
        time.sleep(float(time_val))

    def shutdownHV(self):
        self.vme_easiroc.send_shutdown_hv()

    def setHV(self, value):
        self.vme_easiroc.send_madc_control()
        self.vme_easiroc.send_hv_control(float(value))

    def increaseHV(self, value):
        value = float(value)
        if value < 0.0:
            print("Input value must be positive!")
            return
        elif value > 90.0:
            print("Too large input value! Must be smaller than 90.0")
            return

        count = int(value / 10.0)
        for i in range(count + 1):
            self.setHV(i * 10.0)
            time.sleep(1)
            self.checkHV((i + 1) * 10.0, 20.0)
            time.sleep(0.2)
        self.setHV(value)
        time.sleep(1)
        self.checkHV((count + 1) * 10.0, 20.0)
        time.sleep(0.2)

    def decreaseHV(self, value):
        self.vme_easiroc.send_madc_control()
        self.checkHV(value + 10.0, 20.0)
        rd_madc = self.vme_easiroc.read_madc(3)
        count = int(rd_madc / 10.0)
        for i in range(count + 1):
            self.setHV((count - i) * 10.0)
            time.sleep(1)
            self.checkHV((count - i + 1) * 10.0, 20.0)
            time.sleep(0.2)
        self.setHV(0.0)
        time.sleep(1)
        self.checkHV(10.0, 20.0)
        time.sleep(0.2)

    def initialCheck(self):
        self.vme_easiroc.send_madc_control()
        self.checkHV(10.0, 20.0)
        time.sleep(0.2)
        self.setHV(2.0)
        time.sleep(1)
        self.checkHV(10.0, 20.0)
        time.sleep(0.2)
        self.setHV(3.0)
        time.sleep(1)
        self.checkHV(10.0, 20.0)
        time.sleep(0.2)
        self.setHV(5.0)
        time.sleep(1)
        self.checkHV(10.0, 20.0)
        time.sleep(0.2)
        self.setHV(10.0)
        time.sleep(1)
        self.checkHV(20.0, 20.0)
        time.sleep(0.2)
        self.setHV(0.0)

    def statusHV(self):
        self.vme_easiroc.send_madc_control()

        # Read the MPPC bias voltage
        rd_madc = self.vme_easiroc.read_madc(3)
        print(f"Bias voltage >> {rd_madc:.2f} V")

        # Read the MPPC bias current
        rd_madc = self.vme_easiroc.read_madc(4)
        print(f"Bias current >> {rd_madc:.2f} uA")

    def statusTemp(self):
        self.vme_easiroc.send_madc_control()

        # Read temperature1
        rd_madc = self.vme_easiroc.read_madc(5)
        print(f"Temperature 1 >> {rd_madc:.2f} C")

        # Read temperature2
        rd_madc = self.vme_easiroc.read_madc(0)
        print(f"Temperature 2 >> {rd_madc:.2f} C")

    def statusInputDAC(self, channel, filename="temp"):
        self.vme_easiroc.send_madc_control()

        # Read Input DAC voltage
        ch_int = int(channel)
        read_num = -1

        if 0 <= ch_int <= 63:
            num = ch_int % 32
            read_num = ch_int // 32 + 1
            self.vme_easiroc.set_ch(num)
            rd_madc = self.vme_easiroc.read_madc(read_num)
            print(f"ch {ch_int:2d}: Input DAC >> {rd_madc:.2f} V")
        elif ch_int == 64:
            print("Reading monitor ADC...")
            if not filename.endswith('.yml'):
                filename += '.yml'

            status_filename = f'status/{filename}'
            if not filename.endswith('temp') and os.path.exists(status_filename):
                print(f"{status_filename} already exists.")
                status_filename = f"status/temp_{int(time.time())}.yml"
            print(f"Save as {status_filename}.")

            status = {
                'HV': round(self.vme_easiroc.read_madc(3), 3),
                'Temp': round(self.vme_easiroc.read_madc(5), 3),
                'current': round(self.vme_easiroc.read_madc(4), 3)
            }
            with open(status_filename, 'w') as file:
                yaml.dump(status, file, default_flow_style=False)
            print(f"Read completed, saved to {status_filename}")

    def checkHV(self, vollim=80.0, curlim=20.0, repeat=3):
        self.vme_easiroc.send_madc_control()
        
        vollim = float(vollim)
        curlim = float(curlim)
        repeat = int(repeat)
        check = False
        count = 0
        
        while not check:
            count += 1
            if count > repeat:
                print("Attempt limit reached. Exiting...")
                self.setHV(0.0)
                time.sleep(1)
                sys.exit()
            
            # Read the MPPC bias voltage
            voltage = self.vme_easiroc.read_madc(3)
            
            # Read the MPPC bias current
            current = self.vme_easiroc.read_madc(4)
            
            if voltage > vollim or current > curlim:
                print(f"Over the limit. voltage={voltage:.2f}V, current={current:.2f}uA. Trying again...")
                time.sleep(1)
            else:
                print(f"Status OK. voltage={voltage:.2f}V, current={current:.2f}uA")
                check = True

    def setInputDAC(self, voltage):
        self.vme_easiroc.set_input_dac(float(voltage))
        time.sleep(0.5)
        self.slowcontrol()

    def setRegister(self, key, value):
        self.vme_easiroc.set_register(key, value)
        time.sleep(0.5)
        self.slowcontrol()

    def testChargeTo(self, ch):
        chi = int(ch)
        if chi > 63:
            print('Wrong argument, must be ch < 64')
            return
        
        value = [0] * 32  # Initialize list with 32 zeros

        if chi < 0:
            self.vme_easiroc.set_easiroc1_slow_control("DisablePA & In_calib_EN", value)
            self.vme_easiroc.set_easiroc2_slow_control("DisablePA & In_calib_EN", value)
        elif chi < 32:
            self.vme_easiroc.set_easiroc2_slow_control("DisablePA & In_calib_EN", value)
            value[chi] = 1
            self.vme_easiroc.set_easiroc1_slow_control("DisablePA & In_calib_EN", value)
        else:
            self.vme_easiroc.set_easiroc1_slow_control("DisablePA & In_calib_EN", value)
            chi -= 32
            value[chi] = 1
            self.vme_easiroc.set_easiroc2_slow_control("DisablePA & In_calib_EN", value)

    def setThreshold(self, pe, chip="0", filename="temp"):
        self.vme_easiroc.set_threshold(pe, chip, filename)
        time.sleep(0.5)
        self.slowcontrol()

    def muxControl(self, chnum):
        self.vme_easiroc.set_ch(int(chnum))

    def slowcontrol(self):
        self.vme_easiroc.reload_setting()
        self.vme_easiroc.send_slow_control()
        self.vme_easiroc.send_probe_register()
        self.vme_easiroc.send_read_register()
        self.vme_easiroc.send_pedestal_suppression()
        self.vme_easiroc.send_selectable_logic()
        self.vme_easiroc.send_trigger_pla()
        self.vme_easiroc.send_trigger_width()
        self.vme_easiroc.send_time_window()
        self.vme_easiroc.send_usr_clk_out_register()
        self.vme_easiroc.send_trigger_values()

    def slowcontrol_only(self):
        self.vme_easiroc.send_slow_control()
        self.vme_easiroc.send_probe_register()
        self.vme_easiroc.send_read_register()
        self.vme_easiroc.send_pedestal_suppression()
        self.vme_easiroc.send_selectable_logic()
        self.vme_easiroc.send_trigger_pla()
        self.vme_easiroc.send_trigger_width()
        self.vme_easiroc.send_time_window()
        self.vme_easiroc.send_usr_clk_out_register()
        self.vme_easiroc.send_trigger_values()

    def adc(self, on_off):
        print(f"Set ADC {on_off}")
        if on_off == 'on':
            self.vme_easiroc.send_adc = True
        elif on_off == 'off':
            self.vme_easiroc.send_adc = False
        else:
            print(f"Unknown argument {on_off}")
            return

    def tdc(self, on_off):
        print(f"Set TDC {on_off}")
        if on_off == 'on':
            self.vme_easiroc.send_tdc = True
        elif on_off == 'off':
            self.vme_easiroc.send_tdc = False
        else:
            print(f"Unknown argument {on_off}")
            return

    def scaler(self, on_off):
        print(f"Set scaler {on_off}")
        if on_off == 'on':
            self.vme_easiroc.send_scaler = True
        elif on_off == 'off':
            self.vme_easiroc.send_scaler = False
        else:
            print(f"Unknown argument {on_off}")
            return

    def stp(self, on_off):
        print(f"Set stp {on_off}")
        if on_off == 'on':
            self.vme_easiroc.send_stp = True
        elif on_off == 'off':
            self.vme_easiroc.send_stp = False
        else:
            print(f"Unknown argument {on_off}")
            return

    def regacyDataFormat(self, on_off):
        print(f"Set regacyDataFormat {on_off}")
        if on_off == 'on':
            self.vme_easiroc.new_format = False
        elif on_off == 'off':
            self.vme_easiroc.new_format = True
        else:
            print(f"Unknown argument {on_off}")
            return

    def setStpMode(self, value):
        print(f"setStpMode {value}")
        self.vme_easiroc.send_stp_mode_register(int(value))

    def setTESTPIN(self, value):
        print(f"setTESTPIN {value}")
        self.vme_easiroc.send_test_pin_register(int(value))

    def setTestCharge(self, value):
        print(f"setTestCharge {value}")
        self.vme_easiroc.send_test_charge_register(int(value))

    def setTriggerMode(self, value):
        print(f"setTriggerMode {value}")
        self.vme_easiroc.send_trigger_mode(int(value))

    def setTriggerDelay(self, value):
        print(f"setTriggerDelay {value}")
        self.vme_easiroc.send_trigger_delay(int(value))

    def standby(self, counts):
        for _ in range(int(counts)):
            buf = self.q.pop()
            print(f"EASIROC {buf} is ready.")
        print("sleep 1 in standby.")
        time.sleep(1)
        print("End of standby.")

    def dummy_read(self, events, dummystring):
        # just for DEBUGGING purpose
        self.stop_requested = False

        for i in range(20):
            if self.stop_requested:
                print("Measurement stopped by user.")
                break
            time.sleep(1)
            print(f'{i}/{events} {dummystring}')
        
    def read(self, events, filename="temp", mode="default"):
        print("Begin of read.")
        events = int(events)
        if not filename.endswith('.dat'):
            filename += '.dat'

        data_filename = f'data/{filename}'
        if "temp" not in filename and os.path.exists(data_filename):
            print(f"{data_filename} already exists.")
            data_filename = f"data/temp_{int(time.time())}.dat"
        print(f"Save as {data_filename} {events} events")

        self.stop_requested = False
        
        if mode == "default":
            with open(data_filename, 'wb') as file:
                with tqdm(total=events, desc="Processing", ncols=100, unit="event") as progress_bar:
                    # Read event data and wirte to output
                    for header, data in self.vme_easiroc.read_event(events):
                        # Stop
                        if self.stop_requested:
                            print("Measurement stopped by user but nothing happen")
                            # break
                        # Add Header
                        file.write(header['header'])
                        # Pack data
                        file.write(struct.pack('!{}I'.format(len(data)), *data))
                        # Update progress bar
                        progress_bar.update(1)
        else:
            print("Invalid mode... 'default'")
            return

        self.slowcontrol()

    def fit(self, filename="temp", *ch):
        status_filename = f"status/{filename}.yml"
        with open(status_filename, 'r') as file:
            status = yaml.safe_load(file)

        if not ch:
            for ich in range(64):
                voltage = status['HV'] - status['InputDAC'][ich]
                subprocess.run([f'root', '-l', '-b', '-q', f'fit1.cpp("{filename}", {voltage}, {ich})'])
        else:
            for ich in map(int, ch):
                voltage = status['HV'] - status['InputDAC'][ich]
                subprocess.run([f'root', '-l', '-b', '-q', f'fit1.cpp("{filename}", {voltage}, {ich})'])

    def drawScaler(self, filename="temp", dac="reg", *ch):
        if dac == "reg":
            dac = self.vme_easiroc.get_register("thr")
        else:
            dac = int(dac)

        if not ch:
            for ich in range(64):
                subprocess.run([f'root', '-l', '-b', '-q', f'scaler1.cpp("{filename}", {dac}, {ich})'])
        else:
            for ich in map(int, ch):
                subprocess.run([f'root', '-l', '-b', '-q', f'scaler1.cpp("{filename}", {dac}, {ich})'])

    def reset(self, target):
        if target not in ['probe', 'readregister', 'pedestalsuppression', 'triggerPla']:
            print(f"Unknown argument {target}")
            return

        if target == 'probe':
            self.vme_easiroc.reset_probe_register()
        elif target == 'readregister':
            self.vme_easiroc.reset_read_register()
        elif target == 'pedestalsuppression':
            self.vme_easiroc.reset_pedestal_suppression()
        elif target == 'triggerPla':
            self.vme_easiroc.reset_trigger_pla()

    def timeStamp(self):
        current_time = time.localtime()
        print(f"Time stamp: {time.strftime('%Y-%m-%d %H:%M:%S', current_time)}, {int(time.time())}")

    def help(self):
        print("""
        How to use:
        setHV <bias voltage>    input <bias voltage>; 0.00~90.00V to MPPC
        slowcontrol             transmit SlowControl
        read <EventNum> <FileName>  read <EventNum> events and write to <FileName>
        reset probe|readregister    reset setting
        help                    print this message
        version                 print version number
        exit|quit               quit this program

        COMMANDS:
        - adc <on/off>
        - cd <path>
        - sleep <time>
        - exit
        - muxControl <ch(0..32)>
        - quit
        - read <EventNum> <FileName>
        - regacyDataFormat <on/off>
        - reset <probe/readregister/pedestalsuppression/triggerPla>
        - scaler <on/off>
        - stp <on/off>
        - setHV  <bias voltage (00.00~90.00)>
        - increaseHV <bias voltage>
        - decreaseHV
        - slowcontrol
        - statusInputDAC <ch(0..63) / all(64)>
        - statusHV
        - statusTemp
        - checkHV <voltage_limit=80><current_limit=20><repeat_count=3>
        - setInputDAC <InputDAC voltage (0.0~4.5)>
        - setStpMode <0~8>
        - setTestCharge <0:CAL2 default, 1:CAL1, 2:CAL2+CAL1>
        - setTriggerMode <0: ,>
        - setTriggerDelay <0: ,>
        - tdc <on/off>
        - version
        - initialCheck
        - read
        - fit
        """)

    def version(self):
        version_major, version_minor, version_hotfix, version_patch, year, month, day = self.vmeEasiroc.version
        print(f"v.{version_major}.{version_minor}.{version_hotfix}-p{version_patch}")
        print(f"Synthesized on {year}-{month}-{day}")

    def quit(self):
        print('DEBUG: stop_requested')
        self.stop_requested = True
        #sys.exit()

    def show_easiroc1(self):
        print("easiroc1.slowControl")
        print(self.vmeEasiroc.easiroc1.slow_control)
        print("Easiroc1SlowControl")
        print(self.vmeEasiroc.get_easiroc1_slow_control())

    def show_easiroc2(self):
        print("easiroc2.slowControl")
        print(self.vmeEasiroc.easiroc2.slow_control)
        print("Easiroc2SlowControl")
        print(self.vmeEasiroc.get_easiroc2_slow_control())

if __name__ == "__main__":
    print(f'KK_DEBUG:Set up Looger') 
    # Logger setup
    logger = logging.getLogger()
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    #logger.setLevel(logging.INFO)
    logger.setLevel(logging.DEBUG)

    # Command-line option parsing
    opts = {}
    parser = optparse.OptionParser()
    parser.add_option('-e', '--execute', dest='command', help='Execute COMMAND')
    parser.add_option('-q', '--quit', dest='quit', action='store_true', help='Quit after executing command')
    (options, args) = parser.parse_args()

    ipaddr = args[0] if args else "192.168.10.18"
    if not ipaddr:
        print("Usage: {} <Options> <IP Address>".format(sys.argv[0]))
        sys.exit(1)

    print(f'KK_DEBUG:Int VME Easiroc: {ipaddr}') 
    vmeEasiroc = VmeEasiroc(ipaddr, 24, 4660, 'yaml_parent')
    vmeEasiroc.send_slow_control()
    vmeEasiroc.send_probe_register()
    vmeEasiroc.send_read_register()
    
    # Call other initialization functions as needed
    path_of_this_file = os.path.abspath(os.path.dirname(__file__))
    print(f'KK_DEBUG:Init CommandDispatcher: {path_of_this_file}') 
    que = Queue()
    command_dispatcher = CommandDispatcher(vmeEasiroc, que)

    # Commands excuted initially
    print(f'KK_DEBUG:Run Initial Command: {path_of_this_file}') 
    run_command_file = os.path.join(path_of_this_file, '.rc')
    if os.path.exists(run_command_file):
        with open(run_command_file, 'r') as f:
            for line in f:
                print(f'commands from .rc file:{line}')
                command_dispatcher.dispatch(line.strip())

    if options.command:
        for line in options.command.split(';'):
            command_dispatcher.dispatch(line.strip())

    if options.quit:
        print(f'KK_DEBUG: Quit')
        sys.exit(0)

    print(f'KK_DEBUG: Signal handling')
    # Signal handling
    def handle_signal(sig, frame):
        print("!!!! Ctrl+C !!!! 'exit|quit' command is recommended.")
        print("Decreasing MPPC bias voltage...")
        command_dispatcher.setHV(0.00)
        # Add necessary clean-up and shutdown procedures
        sys.exit(0)
    print(f'KK_DEBUG: Signal handling 2')
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTSTP, handle_signal)
    print(f'KK_DEBUG: Signal handling 3')

    # Readline completion (implementing command-line auto-completion)
    readline.set_completer_delims(' \t\n=;')
    readline.set_completer(lambda text, state: [cmd for cmd in CommandDispatcher.COMMANDS if cmd.startswith(text)][state])
    print(f'KK_DEBUG: End of program')
