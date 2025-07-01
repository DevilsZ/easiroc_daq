import yaml
import copy

class ConfigLoader:
    def __init__(self, register_attribute, register_value_alias, default_register_value,
                 register_value, input_dac, pedestal_suppression_value, trigger_pla_value, calibration):
        self.check_hash(register_attribute, register_value_alias, default_register_value)
        self.register_attribute = self.read_yaml(register_attribute)
        self.default_register_value = self.read_yaml(default_register_value)
        self.register_value = self.read_yaml(register_value)
        self.register_value_alias = self.read_yaml(register_value_alias)
        input_dac = self.read_yaml(input_dac)
        self.pedestal_suppression = self.read_yaml(pedestal_suppression_value)
        self.trigger_pla = self.read_yaml(trigger_pla_value)
        self.calibration = self.read_yaml(calibration)

        self.resolve_same()
        self.resolve_alias()

        self.easiroc1_slow_control = copy.deepcopy(self.default_register_value)
        self.overwrite_register_value(self.easiroc1_slow_control, self.register_value['EASIROC1'])
        self.overwrite_register_value(self.easiroc1_slow_control, input_dac['EASIROC1'])

        self.easiroc2_slow_control = copy.deepcopy(self.default_register_value)
        self.overwrite_register_value(self.easiroc2_slow_control, self.register_value['EASIROC2'])
        self.overwrite_register_value(self.easiroc2_slow_control, input_dac['EASIROC2'])

        self.probe_slow_control1 = [self.register_value['Probe 1'], self.register_value['Probe Channel 1']]
        self.probe_slow_control2 = [self.register_value['Probe 2'], self.register_value['Probe Channel 2']]

        self.read_register1 = self.register_value['High Gain Channel 1']
        self.read_register2 = self.register_value['High Gain Channel 2']

        self.usr_clk_out_value = self.register_value['UsrClkOut']
        self.selectable_logic = self.register_value['SelectableLogic']
        self.trigger_values = self.register_value['Trigger']

        self.validate()

    def get_easiroc1_slow_control(self):
        return self.easiroc1_slow_control

    def get_easiroc2_slow_control(self):
        return self.easiroc2_slow_control

    def set_easiroc1_slow_control(self, key, value):
        if key in self.easiroc1_slow_control:
            print('  key is valid.')
            print('  current value:')
            print(self.easiroc1_slow_control.get(key))
            print('  new value=')
            print(value)
            self.easiroc1_slow_control[key] = value

    def set_easiroc2_slow_control(self, key, value):
        if key in self.easiroc2_slow_control:
            print('key is valid.')
            print('current value:')
            print(self.easiroc2_slow_control.get(key))
            print('  new value=')
            print(value)
            self.easiroc2_slow_control[key] = value

    def to_easiroc1_slow_control(self):
        return self.to_easiroc_slow_control(self.easiroc1_slow_control)

    def to_easiroc2_slow_control(self):
        return self.to_easiroc_slow_control(self.easiroc2_slow_control)

    def to_probe1_slow_control(self):
        if self.probe_slow_control1[1] == -1:
            return [0] * 20
        if self.probe_slow_control1[1] > 31:
            return [0] * 20
        return self.to_probe_slow_control(self.probe_slow_control1)

    def to_probe2_slow_control(self):
        if self.probe_slow_control2[1] == -1:
            return [0] * 20
        if self.probe_slow_control2[1] < 32:
            return [0] * 20
        return self.to_probe_slow_control([self.probe_slow_control2[0], self.probe_slow_control2[1] - 32])

    def to_read_register1(self):
        if self.read_register1 == -1:
            return -1
        if self.read_register1 > 31:
            return -1
        return self.read_register1

    def to_read_register2(self):
        if self.read_register2 == -1:
            return -1
        if self.read_register2 < 32:
            return -1
        return self.read_register2 - 32

    def to_pedestal_suppression(self):
        return self.pedestal_suppression

    def to_trigger_pla(self):
        return self.trigger_pla

    def to_selectable_logic(self):
        selectable_logic_88bits = [0] * 11
        pattern = self.selectable_logic['Pattern'].split("_")
        if pattern[0] == 'OneCh':
            trigger_channel = int(pattern[1])
            if not (0 <= trigger_channel <= 63):
                print(f"Error: SelectableLogic, 'Pattern: 'OneCh_#' must be 0..63")
                raise ValueError("Invalid trigger channel")
            selectable_logic_88bits[0] = 0
            selectable_logic_88bits[1] = trigger_channel
        else:
            logic_map = {
                'Or32u': 1, 'Or32d': 2, 'Or64': 3, 'Or32And': 4, 'Or16And': 5,
                'And32u': 6, 'And32d': 7, 'And64': 8, 'And32Or': 9
            }
            selectable_logic_88bits[0] = logic_map.get(pattern[0], 0)

        hit_num_th = self.selectable_logic['HitNum Threshold']
        selectable_logic_88bits[2] = hit_num_th

        channels = self.selectable_logic['And Channels']
        and_logic_channels = [channels] if isinstance(channels, int) else list(map(int, channels.split()))
        for i in and_logic_channels:
            if 0 <= i < 64:
                selectable_logic_88bits[10 - i // 8] |= (1 << (i % 8))

        return selectable_logic_88bits

    def to_trigger_width(self):
        if self.trigger_values['Width'] == 'raw':
            return 0
        return (int(self.trigger_values['Width'].split('ns')[0]) - 38) // 8

    def to_trigger_mode(self):
        return self.trigger_values['Mode']

    def to_trigger_delay(self):
        delay1 = int(self.trigger_values['DelayTrigger'])
        delay2 = int(self.trigger_values['DelayHold'])
        delay3 = int(self.trigger_values['DelayL1Trig'])
        return [delay1 if delay1 != -1 else 35,
                delay2 if delay2 != -1 else 8,
                delay3 if delay3 != -1 else 13]

    def to_hv_control(self):
        return self.calibration['HVControl']

    def to_madc_calibration(self):
        return self.calibration['MonitorADC']

    def to_time_window(self):
        return int(self.register_value['TimeWindow'].split('ns')[0])

    def to_usr_clk_out_register(self):
        clk_map = {
            'OFF': 0, 'ON': 1, '1Hz': 2, '10Hz': 3, '100Hz': 4,
            '1kHz': 5, '10kHz': 6, '100kHz': 7, '3MHz': 8
        }
        return clk_map.get(self.usr_clk_out_value, 0)

    def summary(self):
        register_names = [
            "Time Constant HG Shaper", "Time Constant LG Shaper",
            "Capacitor HG PA Fdbck", "Capacitor LG PA Fdbck"
        ]
        easirocs = [
            ["EASIROC1", self.easiroc1_slow_control],
            ["EASIROC2", self.easiroc2_slow_control]
        ]

        ret = ''
        for easiroc in easirocs:
            key, values = easiroc
            ret += f"{key}\n"
            for reg in register_names:
                value = values[reg]
                alias_name = self.register_value_alias.get(reg, {}).get(value, '')
                ret += f"    {reg}: {alias_name}\n"
        return ret

    # Private methods
    def read_yaml(self, file_name):
        with open(file_name, 'r') as file:
            return yaml.safe_load(file)
            
    def overwrite_register_value(self, base, new):
        for key in base:
            if key in new:
                base[key] = new[key]

    def fill_bit(self, array, value, bits_of_value, position):
        bit_num_of_register = 8
        index_of_array = position // bit_num_of_register
        bit_position = position % bit_num_of_register

        if bit_position + bits_of_value > bit_num_of_register:
            num_of_bits_to_store_at_this_time = bit_num_of_register - bit_position
        
            value_to_store_before = value >> num_of_bits_to_store_at_this_time
            bits_of_value_to_store_before = bits_of_value - num_of_bits_to_store_at_this_time
            position_to_store_before = position + num_of_bits_to_store_at_this_time
            self.fill_bit(array, value_to_store_before, bits_of_value_to_store_before, position_to_store_before)
        
            bit_mask = 1
            for _ in range(num_of_bits_to_store_at_this_time - 1):
                bit_mask <<= 1
                bit_mask |= 1
        
            value &= bit_mask
            bits_of_value = num_of_bits_to_store_at_this_time

        bit_mask = 1
        for _ in range(bits_of_value - 1):
            bit_mask <<= 1
            bit_mask |= 1
        bit_mask_shift = bit_mask << bit_position

        array[index_of_array] &= ~bit_mask_shift
        array[index_of_array] |= (value & bit_mask) << bit_position

    def reverse_lsb_and_msb(self, value, bits_of_value):
        ret = 0
        for i in range(bits_of_value):
            if value & (1 << i) != 0:
                ret |= (1 << (bits_of_value - i - 1))
        return ret

    def to_easiroc_slow_control(self, easiroc_slow_control):
        bin_data = [0] * 57
        bit_counter = 0
        #print(f'DEBUG(register_attribute):{self.register_attribute}')
        for register in self.register_attribute:
            #print(f'DEBUG(this register_attribute):{register}')
            name, attribute = register
            value = easiroc_slow_control[name]
        
            if isinstance(value, int):
                bit_counter = self.fill_register_value(bin_data, value, attribute, bit_counter)
            elif isinstance(value, list):
                for i in value:
                    bit_counter = self.fill_register_value(bin_data, i, attribute, bit_counter)

        bin_data = [self.reverse_lsb_and_msb(i, 8) for i in bin_data]
        return bin_data[::-1]

    def to_probe_slow_control(self, probe_slow_control):
        bin_data = [0] * 20
        if probe_slow_control[0] == 'Out_PA_HG':
            bit_to_set = probe_slow_control[1] * 2
        elif probe_slow_control[0] == 'Out_PA_LG':
            bit_to_set = probe_slow_control[1] * 2 + 1
        elif probe_slow_control[0] == 'Out_ssh_HG':
            bit_to_set = 64 + probe_slow_control[1] * 2
        elif probe_slow_control[0] == 'Out_ssh_LG':
            bit_to_set = 64 + probe_slow_control[1] * 2 + 1
        elif probe_slow_control[0] == 'Out_fs':
            bit_to_set = 128 + probe_slow_control[1]
    
        self.fill_bit(bin_data, 1, 1, bit_to_set)
        bin_data = [self.reverse_lsb_and_msb(i, 8) for i in bin_data]
        return bin_data[::-1]

    def fill_register_value(self, bin_data, value, attribute, bit_counter):
        #print(f'DEBUG:{attribute}')
        if attribute.get('BitOrder') == 'MSBtoLSB':
            value = self.reverse_lsb_and_msb(value, attribute['Bits'])
        if attribute['ActiveLow']:
            value ^= (2**attribute['Bits'] - 1)
    
        self.fill_bit(bin_data, value, attribute['Bits'], bit_counter)
        return bit_counter + attribute['Bits']

    def resolve_same(self):
        for name, value in self.register_value['EASIROC2'].items():
            if value == 'same':
                self.register_value['EASIROC2'][name] = self.register_value['EASIROC1'][name]

    def resolve_alias(self):
        self.resolve_alias_sub(self.register_value['EASIROC1'])
        self.resolve_alias_sub(self.register_value['EASIROC2'])
        self.resolve_alias_sub(self.default_register_value)

    def resolve_alias_sub(self, register_value):
        #print('DEBUG1:',register_value.keys())
        #print('DEBUG2:',self.register_value_alias.keys())
        for name, value in register_value.items():
            if isinstance(value, str):
                #print(f'DEBUG3:{name},{value}')
                value_alias = next(
                    (v for k, v in self.register_value_alias[name].items() if k == value), None)
                if value_alias:
                    register_value[name] = value_alias
            else:
                pass
                #print(f'DEBUG4:{name},{value}')
    def validate(self):
        self.validate_class()
        self.validate_register_name()
        self.validate_register_value()
        self.validate_probe()
        self.validate_read_register()
        self.validate_pedestal_suppression()
        self.validate_trigger_pla()
        self.validate_selectable_logic()
        self.validate_time_window()
        self.validate_usr_clk_out()
        self.validate_trigger_values()
        self.validate_calibration()

    def validate_class(self):
        if not isinstance(self.register_value, dict):
            print("Error: RegisterValue file structure error")
            raise ValueError("RegisterValue file structure error")

        setting_names = [
            'EASIROC1', 'EASIROC2', 'Probe 1', 'Probe Channel 1', 'Probe 2', 'Probe Channel 2',
            'High Gain Channel 1', 'High Gain Channel 2', 'SelectableLogic', 'TimeWindow', 'UsrClkOut', 'Trigger'
        ]
        if not all(name in self.register_value for name in setting_names):
            print("Error: RegisterValue file structure error")
            raise ValueError("RegisterValue file structure error")

        setting_classes = [dict, dict, str, int, str, int, int, int, dict, str, str, dict]
        if setting_classes != [type(self.register_value[name]) for name in setting_names]:
            print("Error: RegisterValue file structure error")
            raise ValueError("RegisterValue file structure error")

    def validate_register_name(self):
        register_names = [i[0] for i in self.register_attribute]
        register_value_names_1 = self.register_value['EASIROC1'].keys()
        register_value_names_2 = self.register_value['EASIROC2'].keys()

        invalid_names_1 = set(register_value_names_1) - set(register_names)
        if invalid_names_1:
            print("Error: following register names are incorrect")
            print(invalid_names_1)
            raise ValueError("Invalid register names")

        invalid_names_2 = set(register_value_names_2) - set(register_names)
        if invalid_names_2:
            print("Error: following register names are incorrect")
            print(invalid_names_2)
            raise ValueError("Invalid register names")

    def validate_register_value(self):
        self.validate_register_value_sub(self.register_value['EASIROC1'])
        self.validate_register_value_sub(self.register_value['EASIROC2'])

    def validate_register_value_sub(self, register_value):
        for name, value in register_value.items():
            attribute = next(i[1] for i in self.register_attribute if i[0] == name)

            if 'Array' in attribute:
                if not isinstance(value, list):
                    print(f"Error: {name} must be Array")
                    raise ValueError(f"{name} must be Array")
                
                max_value = 2 ** attribute['Bits'] - 1
                for i in value:
                    if not (0 <= i <= max_value):
                        print(f"Error: element of {name} must be between {0} and {max_value}")
                        raise ValueError(f"Element of {name} must be between {0} and {max_value}")
            else:
                if not isinstance(value, int):
                    print(f"Error: {name} must be an integer (Fixnum)")
                    raise ValueError(f"{name} must be an integer (Fixnum)")

                max_value = 2 ** attribute['Bits'] - 1
                if not (0 <= value <= max_value):
                    print(f"Error: {name} must be between {0} and {max_value}")
                    raise ValueError(f"{name} must be between {0} and {max_value}")

    def validate_probe(self):
        probe_names = ['Out_PA_HG', 'Out_PA_LG', 'Out_ssh_HG', 'Out_ssh_LG', 'Out_fs']
        if self.register_value['Probe 1'] not in probe_names:
            print("Error: Probe 1 must be one of Out_PA_HG, Out_PA_LG, Out_ssh_HG, Out_ssh_LG, Out_fs")
            raise ValueError("Invalid Probe 1")

        if self.register_value['Probe 2'] not in probe_names:
            print("Error: Probe 2 must be one of Out_PA_HG, Out_PA_LG, Out_ssh_HG, Out_ssh_LG, Out_fs")
            raise ValueError("Invalid Probe 2")

        channel1 = self.register_value['Probe Channel 1']
        if not (-1 <= channel1 <= 31):
            print("Error: Probe Channel 1 must be between 0 and 31, or -1")
            raise ValueError("Invalid Probe Channel 1")

        channel2 = self.register_value['Probe Channel 2']
        if not (32 <= channel2 <= 63 or channel2 == -1):
            print("Error: Probe Channel 2 must be between 32 and 63, or -1")
            raise ValueError("Invalid Probe Channel 2")

    def validate_read_register(self):
        channel1 = self.register_value['High Gain Channel 1']
        if not (-1 <= channel1 <= 31):
            print("Error: High Gain Channel 1 must be between 0 and 31, or -1")
            raise ValueError("Invalid High Gain Channel 1")

        channel2 = self.register_value['High Gain Channel 2']
        if not (32 <= channel2 <= 63 or channel2 == -1):
            print("Error: High Gain Channel 2 must be between 32 and 63, or -1")
            raise ValueError("Invalid High Gain Channel 2")

    def validate_pedestal_suppression(self):
        if sorted(self.pedestal_suppression.keys()) != ['HG', 'LG']:
            print('Error: PedestalSuppression file syntax error')
            raise ValueError('PedestalSuppression file syntax error')

        if len(self.pedestal_suppression['HG']) != 64:
            print('Error: PedestalSuppression file syntax error')
            raise ValueError('PedestalSuppression file syntax error')

        if len(self.pedestal_suppression['LG']) != 64:
            print('Error: PedestalSuppression file syntax error')
            raise ValueError('PedestalSuppression file syntax error')

        for v in self.pedestal_suppression.values():
            if not all(0 <= th <= 4095 for th in v):
                print('Error: PedestalSuppression Threshold must be between 0 and 4095')
                raise ValueError('PedestalSuppression Threshold must be between 0 and 4095')

    def validate_trigger_pla(self):
        if sorted(self.trigger_pla.keys()) != ['AndLogicCh1x', 'AndLogicCh2x', 'C_moni1', 'C_moni2', 'Channel', 'Cmd', 'OrLogicCh1x', 'OrLogicCh2x']:
            print('Error: TriggerPla file syntax error')
            raise ValueError('TriggerPla file syntax error')

        if len(self.trigger_pla['AndLogicCh1x']) != 16:
            print('Error: TriggerPla file syntax error')
            raise ValueError('TriggerPla file syntax error')

        if len(self.trigger_pla['AndLogicCh2x']) != 16:
            print('Error: TriggerPla file syntax error')
            raise ValueError('TriggerPla file syntax error')

        if len(self.trigger_pla['OrLogicCh1x']) != 4:
            print('Error: TriggerPla file syntax error')
            raise ValueError('TriggerPla file syntax error')

        if len(self.trigger_pla['OrLogicCh2x']) != 4:
            print('Error: TriggerPla file syntax error')
            raise ValueError('TriggerPla file syntax error')

        cmd = self.trigger_pla['Cmd']
        if not (cmd == 0x80 or 0 <= cmd <= 8):
            print("Error: TriggerPla 'Cmd' must be 0..8 or 0x80")
            raise ValueError("Invalid TriggerPla 'Cmd'")

        channel = self.trigger_pla['Channel']
        if not (0 <= channel <= 63):
            print("Error: TriggerPla 'Channel' must be 0..63")
            raise ValueError("Invalid TriggerPla 'Channel'")

        for key in ['C_moni1', 'C_moni2']:
            channel = self.trigger_pla[key]
            if not (0 <= channel <= 63):
                print(f"Error: TriggerPla '{key}' must be 0..63")
                raise ValueError(f"Invalid TriggerPla '{key}'")

    def validate_selectable_logic(self):
        selectableLogic = self.register_value['SelectableLogic']
        
        settingNames = ['Pattern', 'HitNum Threshold', 'And Channels']
        if not all(name in selectableLogic for name in settingNames):
            print("Error: SelectableLogic register parameter structure error")
            raise ValueError("SelectableLogic register parameter structure error")
        
        patternName = ['OneCh', 'Or32u', 'Or32d', 'Or64', 'Or32And', 'Or16And',
                       'And32u', 'And32d', 'And64', 'And32Or']
        
        if selectableLogic['Pattern'].split('_')[0] not in patternName:
            print("Error: SelectableLogic, 'Pattern' must be 'OneCh_#','Or32u','Or32d','Or64','Or32And','Or16And','And32u','And32d','And64','And32Or'")
            raise ValueError("Invalid Pattern value in SelectableLogic")

        if isinstance(selectableLogic['HitNum Threshold'], int):
            if not (0 <= selectableLogic['HitNum Threshold'] <= 64):
                print('Error: SelectableLogic, "HitNum Threshold" must be between 64 and 0')
                raise ValueError('Invalid HitNum Threshold value')
        else:
            print('Error: SelectableLogic, "HitNum Threshold" must be between 64 and 0')
            raise ValueError('Invalid HitNum Threshold type')
        
        andChannels = selectableLogic['And Channels']
        if isinstance(andChannels, int):
            if not (-1 <= andChannels <= 63):
                print("Error: SelectableLogic, 'And Channels': must be 0..63 or -1")
                raise ValueError("Invalid And Channels value")
        else:
            for i in andChannels.split(" "):
                if not i.isdigit():
                    print("Error:SelectableLogic 'And Channels': must be 0..63 or -1")
                    raise ValueError("Invalid And Channels value")
                if not (0 <= int(i) <= 63):
                    print("Error:SelectableLogic 'And Channels': must be 0..63 or -1")
                    raise ValueError("Invalid And Channels value")
        
    def validate_trigger_values(self):
        mode = self.trigger_values['Mode']
        if not isinstance(mode, int) or not (0 <= mode <= 7):
            print('Error: Trigger(Mode) must be 0 - 7.')
            raise ValueError('Invalid Mode value')

        delay = [self.trigger_values['DelayTrigger'],
                 self.trigger_values['DelayHold'],
                 self.trigger_values['DelayL1Trig']]
        for i in delay:
            if not (-1 <= i <= 253 and i != 0):
                print('Error: Trigger(Delay) must be -1 or 1 - 253')
                raise ValueError('Invalid Delay value')
        
        widthValue = self.trigger_values['Width'].split('ns')[0]
        if widthValue != 'raw':
            if not (40 <= int(widthValue) <= 800):
                print('Error: Trigger(Width) must be "raw" or "40ns - 800ns"')
                raise ValueError('Invalid Width value')

    def validate_time_window(self):
        timeWindow = self.register_value['TimeWindow'].split('ns')[0]
        if not timeWindow.isdigit() or not (0 <= int(timeWindow) <= 4095):
            print('Error: TimeWindow must be between "4095ns" and "0ns"')
            raise ValueError('Invalid TimeWindow value')

    def validate_usr_clk_out(self):
        usrClkOutNames = ['OFF', 'ON', '1Hz', '10Hz', '100Hz', '1kHz', '10kHz', '100kHz', '3MHz']
        if self.register_value['UsrClkOut'] not in usrClkOutNames:
            print('Error: UsrClkOut must be "OFF, ON, 1Hz, 10Hz, 100Hz, 1kHz, 10kHz, 100kHz, 3MHz"')
            raise ValueError('Invalid UsrClkOut value')

    def validate_calibration(self):
        settingNames = ['HVControl', 'MonitorADC']
        if not all(name in self.calibration for name in settingNames):
            print("Error: Calibration parameter structure error. 'HVControl' and 'MonitorADC'")
            raise ValueError("Calibration structure error")

        settingMadcNames = ['HV', 'Current', 'InputDac', 'Temperature']
        if not all(name in self.calibration['MonitorADC'] for name in settingMadcNames):
            print("Error: Calibration 'MonitorADC' parameter structure error. 'HV, Current, InputDac, Temperature'")
            raise ValueError("MonitorADC structure error")

        for x in self.calibration['HVControl']:
            if not isinstance(x, float):
                print("Error: Calibration 'HVControl' parameters must be Float.")
                raise ValueError("Invalid HVControl value")

        for x in self.calibration['MonitorADC'].values():
            if not isinstance(x, float):
                print("Error: Calibration 'MonitorADC' parameters must be Float.")
                raise ValueError("Invalid MonitorADC value")
                    
    def check_hash(self, *args):
        for arg in args:
            if not isinstance(arg, str):
                raise ValueError("All arguments must be strings.")
