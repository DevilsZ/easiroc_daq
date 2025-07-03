import tkinter as tk
from tkinter import ttk

import sys
import os
import logging
import signal
import readline
import time
import subprocess
import yaml
import optparse
import time

import threading

from queue import Queue
from datetime import datetime
from tqdm import tqdm

from VME_EASIROC import VmeEasiroc
from Controller import CommandDispatcher

# Set environment variable equivalent to ENV['INLINEDIR']
os.environ['INLINEDIR'] = os.path.dirname(os.path.abspath(__file__))

class VmeEasirocGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VME Easiroc Control")
        
        # Variables
        self.queue = {}
        self.queue['main'] = Queue()
        self.ipaddr1 = tk.StringVar(value="192.168.10.18")
        self.ipaddr2 = tk.StringVar(value="192.168.10.17")
        self.easiroc_modules = {}
        self.dispatcher = {}
        # Status texts
        self.status = {} 
        self.status['parent'] = tk.StringVar(value="Status: Not Connected") # Status for Module 1
        self.status['child']  = tk.StringVar(value="Status: Not Connected") # Status for Module 2

        self.daq_running = False

        row_counter = 0
        # GUI Elements
        # IP Address Input and Connection Button
        # Module 1
        ttk.Label(root, text="IP Address for Module 1:").grid(row=row_counter+0, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Entry(root, textvariable=self.ipaddr1, width=20).grid(row=row_counter+1, column=0, padx=10, pady=5)
        #ttk.Button(root, text="Connect", command=self.connect('parent', self.ipaddr1.get())).grid(row=row_counter+1, column=1, padx=10, pady=5)
        ttk.Button(root, text="Connect", command=lambda: self.connect('parent', self.ipaddr1.get())).grid(row=row_counter+1, column=1, padx=10, pady=5)
        # Status for Module 1
        ttk.Label(root, textvariable=self.status['parent']).grid(row=row_counter+2, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W)
        # Module 2
        ttk.Label(root, text="IP Address for Module 2:").grid(row=row_counter+0, column=2, padx=10, pady=5, sticky=tk.W)
        ttk.Entry(root, textvariable=self.ipaddr2, width=20).grid(row=row_counter+1, column=2, padx=10, pady=5)
        ttk.Button(root, text="Connect", command=lambda: self.connect('child', self.ipaddr2.get())).grid(row=row_counter+1, column=3, padx=10, pady=5)
        # Status for Module 2
        ttk.Label(root, textvariable=self.status['child']).grid(row=row_counter+2, column=2, columnspan=2, padx=10, pady=5, sticky=tk.W)

        upper_line = ttk.Separator(root, orient="horizontal")
        upper_line.grid(row=row_counter+3, column=0, columnspan=10, sticky="ew", pady=10)

        # Let's set row counter again
        row_counter = 4
        
        # Method Buttons
        """
        Let's add important command to these buttons
        - Increse HV
        - read {nevents} {filename}
        - Stop daq
        - Shutdown HV? 1. SetHV(0.0) 2. ShutdownHV
        """
        ttk.Label(root, text="Send Command for Module 1").grid(row=row_counter+0, column=0, columnspan=2, padx=10, pady=5, sticky=tk.W)
        ttk.Label(root, text="Send Command for Module 2").grid(row=row_counter+0, column=2, columnspan=2, padx=10, pady=5, sticky=tk.W)
        # Set HV using increaseHV
        self.HV_module1 = tk.DoubleVar(value=41.0)
        ttk.Entry(root, textvariable=self.HV_module1, width=10).grid(row=row_counter+1, column=0, padx=10, pady=5)
        ttk.Button(root, text="Set HV",  command=lambda: self.dispatch1('parent', 'increaseHV', self.HV_module1.get())).grid(row=row_counter+1, column=1, padx=10, pady=5)
        self.HV_module2 = tk.DoubleVar(value=43.0)
        ttk.Entry(root, textvariable=self.HV_module2, width=10).grid(row=row_counter+1, column=2, padx=10, pady=5)
        ttk.Button(root, text="Set HV",  command=lambda: self.dispatch1('child', 'increaseHV', self.HV_module2.get())).grid(row=row_counter+1, column=3, padx=10, pady=5)
        # To shutdown HVs
        ttk.Button(root, text="Shutdown HV", command=lambda: self.dispatch0('parent', 'shutdownHV')).grid(row=row_counter+2, column=1, padx=10, pady=5)
        ttk.Button(root, text="Shutdown HV", command=lambda: self.dispatch0('child',  'shutdownHV')).grid(row=row_counter+2, column=3, padx=10, pady=5)

        # Main DAQ control
        middle_line = ttk.Separator(root, orient="horizontal")
        middle_line.grid(row=row_counter+3, column=0, columnspan=4, sticky="ew", pady=10)

        # Let's set row counter again
        row_counter = 8
        ttk.Label(root, text="Main DAQ control").grid(row=row_counter, column=0, columnspan=4, padx=10, pady=5, sticky=tk.W)

        # Inupt parameters
        self.nevents = tk.IntVar()
        self.nevents.set(100)
        self.filename = tk.StringVar()
        self.filename.set('test')
        ttk.Label(root, text="Number of events").grid(row=row_counter+1, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Entry(root, textvariable=self.nevents, width=10).grid(row=row_counter+2, column=0, padx=10, pady=5)
        ttk.Label(root, text="File name to saved").grid(row=row_counter+1, column=1, padx=10, pady=5, sticky=tk.W)
        ttk.Entry(root, textvariable=self.filename, width=10).grid(row=row_counter+2, column=1, padx=10, pady=5)
        # START DAQ
        self.start_button = ttk.Button(root, text="Start DAQ", command=lambda: self.start_daq(self.nevents.get(), self.filename.get()))
        self.start_button.grid(row=row_counter+2, column=2, padx=10, pady=10)
        # STOP DAQ
        self.stop_button = ttk.Button(root, text="!!STOP!!", command=lambda: self.stop_daq())
        self.stop_button.grid(row=row_counter+2, column=3, padx=10, pady=10)

        bottom_line = ttk.Separator(root, orient="horizontal")
        bottom_line.grid(row=row_counter+3, column=0, columnspan=4, sticky="ew", pady=10)

        # Let's set row counter again
        row_counter = 12

        ## Command Input
        self.command1 = tk.StringVar()
        self.command2 = tk.StringVar()
        ttk.Label(root, text="Dispatch your own command:").grid(row=row_counter+0, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Label(root, text="Dispatch your own command:").grid(row=row_counter+0, column=2, padx=10, pady=5, sticky=tk.W)
        # Entry
        ttk.Entry(root, textvariable=self.command1, width=20).grid(row=row_counter+1, column=0, padx=10, pady=5)
        ttk.Entry(root, textvariable=self.command2, width=20).grid(row=row_counter+1, column=2, padx=10, pady=5)
        # Buttons
        ttk.Button(root, text="Dispatch Command", command = lambda: self.dispatch_command('parent', self.command1.get())).grid(row=row_counter+1, column=1, padx=10, pady=5)
        ttk.Button(root, text="Dispatch Command", command = lambda: self.dispatch_command('child',  self.command2.get())).grid(row=row_counter+1, column=3, padx=10, pady=5)

        # Dispatc command from the list
        ttk.Label(root, text="Dispatch command from list:").grid(row=row_counter+2, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Label(root, text="Argument:").grid(row=row_counter+2, column=1, padx=10, pady=5, sticky=tk.W)

        # Create Combobox
        values = ["testChargeTo", "setTestCharge", "setTESTPIN", "Command 4"]
        self.combobox = ttk.Combobox(root, values=values, state="readonly")
        self.combobox.grid(row=row_counter+3, column=0, padx=10, pady=5, sticky=tk.W)
        self.combobox.set("None")
        # argument
        self.argument = tk.StringVar()
        self.argument.set('None')
        ttk.Entry(root, textvariable=self.argument, width=20).grid(row=row_counter+3, column=1, padx=10, pady=5)
        # module
        modules = ["parent", "child"]
        self.combobox2 = ttk.Combobox(root, values=modules, state="readonly")
        self.combobox2.grid(row=row_counter+3, column=2, padx=10, pady=5, sticky=tk.W)
        self.combobox2.set("parent")
        ttk.Button(root, text="Execute", command=self.on_select).grid(row=row_counter+3, column=3, padx=10, pady=5, sticky=tk.W)
        #ttk.Button(root, text="Execute", command = lambda: self.dispatch_command('parent', self.command1.get())).grid(row=row_counter+3, column=2, padx=10, pady=5, sticky=tk.W)
        #self.combobox.bind("<<ComboboxSelected>>", self.on_select)

        # Let's set row counter again
        row_counter = 23
        
        # redirect STDOUT to a text field
        self.root.grid_rowconfigure(23, weight=1)  # Enable row 11 to resize
        for col in range(4):  # Enable all columns to resize
            self.root.grid_columnconfigure(col, weight=1)
        
        self.output_frame = ttk.Frame(root)
        self.output_frame.grid(row=row_counter, column=0,  columnspan=4, padx=10, pady=10, sticky="nsew")

        self.text = tk.Text(self.output_frame, height=8, wrap="word")
        self.text.grid(row=row_counter, column=0, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self.output_frame, orient="vertical", command=self.text.yview)
        self.scrollbar.grid(row=row_counter, column=1, sticky="ns")
        self.text.configure(yscrollcommand=self.scrollbar.set)

        # resize field to fit whole frame
        self.output_frame.grid_rowconfigure(0, weight=1)
        self.output_frame.grid_columnconfigure(0, weight=1)

        # redirect stdout to a field and stdout
        self.original_stdout = sys.stdout
        sys.stdout = TextRedirector(self.text, self.original_stdout, self.queue['main'])

        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Periodically check and process queue
        self.process_queue()
        
    def connect(self, name, ipaddr):
        """Connect to VME Easiroc."""
        if name in self.easiroc_modules:
            self.status[name].config(text=f"Error: {name} is already connected.")
            return
        try:
            # Easiroc instance
            print(f'Establishing connection to {name} module with ipaddr={ipaddr}')
            vme_instance = VmeEasiroc(ipaddr, 24, 4660, 'yaml_'+name)
            self.easiroc_modules[name] = vme_instance
            self.easiroc_modules[name].send_slow_control()
            self.easiroc_modules[name].send_probe_register()
            self.easiroc_modules[name].send_read_register()
            self.easiroc_modules[name].send_pedestal_suppression()
            self.easiroc_modules[name].send_selectable_logic()
            self.easiroc_modules[name].send_trigger_pla()
            self.easiroc_modules[name].send_trigger_width()
            self.easiroc_modules[name].send_time_window()
            self.easiroc_modules[name].send_usr_clk_out_register()
            self.easiroc_modules[name].send_trigger_values()
            self.easiroc_modules[name].new_format = True
 
            # Queue
            queue = Queue()
            self.queue[name] = queue
            # Dispatcher
            dispatcher = CommandDispatcher(self.easiroc_modules[name], self.queue[name])
            self.dispatcher[name] = dispatcher

            # Commands excuted initially
            run_command_file = os.path.join('.rc')
            if os.path.exists(run_command_file):
                with open(run_command_file, 'r') as f:
                    for line in f:
                        self.dispatcher[name].dispatch(line.strip())
            
            # 
            self.status[name].set(f'Status: Connected to {name}:{ipaddr}')
        except Exception as e:
            self.status[name].set(f"Error: {e}")
            
    def set_HV(self, name, value): # obsolute method
        """Set HV using increaseHV function"""
        print(f'Set HV to {value} on module {name}')
        self.dispatcher[name].increaseHV(value)
 
    def start_daq(self, nevents, filename):
        self.daq_running = True

        outputfilename1 = f'{filename}_1.dat'
        outputfilename2 = f'{filename}_2.dat'
        print(f'Start DAQ: output files:{outputfilename1}, {outputfilename2}')
        commandname1 = f'read {nevents} {outputfilename1} default'
        commandname2 = f'read {nevents} {outputfilename2} default'

        # excute command within threads
        process1 = threading.Thread(target=self.dispatcher['parent'].dispatch, args=(commandname1,))
        process2 = threading.Thread(target=self.dispatcher['child'].dispatch,  args=(commandname2,))

        # Start processes
        process1.start()
        time.sleep(0.1) # slight delay
        process2.start()

        # Wait end of process --> Unstable 
        # process1.join()
        # process2.join()
        
        self.daq_running = False

    def stop_daq(self):
        self.daq_running = False

        print("STOP button pressed. Attempting to stop measurement...")
        if 'parent' in self.dispatcher:
            self.dispatcher['parent'].dispatch('quit')
        if 'child' in self.dispatcher:
            self.dispatcher['child'].dispatch('quit')
    
    def dispatch0(self, name, command):
        """Dispatch a command with no argument using CommandDispatcher."""
        if self.dispatcher[name]:
            commandname = f'{command}'
            self.dispatcher[name].dispatch(commandname)
        else:
            print(f'Error: module_{name} not connected')
        
    def dispatch1(self, name, command, argv1):
        """Dispatch a command with one argument using CommandDispatcher."""
        if self.dispatcher[name]:
            commandname = f'{command} {argv1}'
            self.dispatcher[name].dispatch(commandname)
        else:
            print(f'Error: module_{name} not connected')

    def dispatch2(self, name, command, argv1, argv2):
        """Dispatch a command with two argument using CommandDispatcher."""
        if self.dispatcher[name]:
            commandname = f'{command} {argv1} {argv2}'
            self.dispatcher[name].dispatch(commandname)
        else:
            print(f'Error: module_{name} not connected')

    def dispatch3(self, name, command, argv1, argv2, argv3):
        """Dispatch a command with three argument using CommandDispatcher."""
        if self.dispatcher[name]:
            commandname = f'{command} {argv1} {argv2} {argv3}'
            self.dispatcher[name].dispatch(commandname)
        else:
            print(f'Error: module_{name} not connected')

    def send_slow_control(self, name):
        """Call send_slow_control method."""
        if self.easiroc_modules[name]:
            self.easiroc_modules[name].send_slow_control()
            self.status[name].set("Slow Control Sent")
        else:
            self.status[name].set("Error: Not Connected")

    def send_probe_register(self, name):
        """Call send_probe_register method."""
        if self.easiroc_modules[name]:
            self.easiroc_modules[name].send_probe_register()
            self.status[name].set("Probe Register Sent")
        else:
            self.status[name].set("Error: Not Connected")

    def send_read_register(self, name):
        """Call send_read_register method."""
        if self.easiroc_modules[name]:
            self.easiroc_modules[name].send_read_register()
            self.status[name].set("Read Register Sent")
        else:
            self.status[name].set("Error: Not Connected")

    def dispatch_command(self, name, command):
        """Dispatch a command using CommandDispatcher."""
        if self.dispatcher[name]:
            self.dispatcher[name].dispatch(command)
            self.status[name].set(f"Command '{command}' Dispatched")
        else:
            self.status[name].set("Error: Not Connected")

    def on_select(self):
        selected_value = self.combobox.get()
        argument = self.argument.get()
        module = self.combobox2.get()
        if module != "parent" and module != "child":
            print(f"Invalid module: {module}")
            return
        
        print(f"Command: {selected_value} {argument} {module}")
        if selected_value == "None":
            print(f"Please select your commnad {selected_value}")
        else:
            if argument == 'None':
                print(f'please set argument {argument}')
            else:
                print(f'Executing command: {selected_value} {argument} {module}')
                self.dispatch1(module, selected_value, argument)

    def process_queue(self):
        # Process all messages in each queue
        for key, q in self.queue.items():  # self.queue = {'parent': Queue(), 'child': Queue(), 'main': Queue()}
            while not q.empty():
                message = q.get_nowait()  # Retrieve the next message
                self.text.insert("end", f"[{key}] {message}\n")  # Display the message with a label
                self.text.see("end")  # Auto-scroll to the end
        
    def on_close(self):
        """Handle application close event."""
        if self.easiroc_modules:
            for key in self.easiroc_modules.keys():
                try:
                    self.status[key].set("Resetting device...")
                    # Example of a reset method; replace with your actual reset logic.
                    self.dispatcher[key].setHV(0.00)  # Set HV to 0.00 as part of reset.
                    self.status[key].set("Device reset successful.")
                    time.sleep(1)
                except Exception as e:
                    self.status[key].set(f"Error during reset: {e}")
                    
        # Exit the application
        self.root.destroy()

class TextRedirector:
    def __init__(self, text_widget, original_stdout, queue):
        self.text_widget = text_widget
        self.original_stdout = original_stdout
        self.queue = queue
        
    def write(self, message):
        self.queue.put(message)
        self.text_widget.insert("end", message)
        self.text_widget.see("end")

        self.original_stdout.write(message)

    def flush(self):
        self.original_stdout.flush() 
        
# Main Application
if __name__ == "__main__":
    root = tk.Tk()
    app = VmeEasirocGUI(root)
    root.mainloop()

