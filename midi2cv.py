class SimpleMIDIDecoder:
    
    def __init__(self, idx=-1):
        self.idx = idx
        self.ch = 0
        self.cmd = 0
        self.d1 = 0
        self.d2 = 0
        self.cbThruFn = 0
        self.cbNoteOnFn = 0
        self.cbNoteOffFn = 0
        
    def cbThru (self, callback):
        self.cbThruFn = callback

    def ThruFn (self, ch, cmd, d1, d2, idx):
        if (self.cbThruFn):
            if (idx != -1):
                self.cbThruFn(ch, cmd, d1, d2, idx)
            else:
                self.cbThruFn(ch, cmd, d1, d2)
        else:
            # Default THRU behaviour
            if (d2 == -1):
                print ("Thru ", ch, ":", hex(cmd), ":", d1)
            else:
                print ("Thru ", ch, ":", hex(cmd), ":", d1, ":", d2)
        
    def cbNoteOn (self, callback):
        self.cbNoteOnFn = callback
    
    def NoteOnFn (self, ch, cmd, note, level, idx):
        if (self.cbNoteOnFn):
            if (idx != -1):
                self.cbNoteOnFn(ch, cmd, note, level, idx)
            else:
                self.cbNoteOnFn(ch, cmd, note, level)
        else:
            # Default NoteOn behaviour
            print ("NoteOn ", ch, ":", note, ":", level)
        
    def cbNoteOff (self, callback):
        self.cbNoteOffFn = callback

    def NoteOffFn (self, ch, cmd, note, level, idx):
        if (self.cbNoteOffFn):
            if (idx != -1):
                self.cbNoteOffFn(ch, cmd, note, level, idx)
            else:
                self.cbNoteOffFn(ch, cmd, note, level)
        else:
            # Default NoteOff behaviour
            print ("NoteOff ", ch, ":", note, ":", level)

    def read(self, mb):
        if ((mb >= 0x80) and (mb <= 0xEF)):
            # MIDI Voice Category Message.
            # Action: Start handling Running Status
            
            # Extract the MIDI command and channel (1-16)
            self.cmd = mb & 0xF0
            self.ch = 1 + (mb & 0x0F)
            
            # Initialise the two data bytes ready for processing
            self.d1 = 0
            self.d2 = 0
        elif ((mb >= 0xF0) and (mb <= 0xF7)):
            # MIDI System Common Category Message.
            # These are not handled by this decoder.
            # Action: Reset Running Status.
            self.cmd = 0
        elif ((mb >= 0xF8) and (mb <= 0xFF)):
            # System Real-Time Message.
            # These are not handled by this decoder.
            # Action: Ignore these.
            pass
        else:
            # MIDI Data
            if (self.cmd == 0):
                # No record of what state we're in, so can go no further
                return
            if (self.cmd == 0x80):
                # Note OFF Received
                if (self.d1 == 0):
                    # Store the note number
                    self.d1 = mb
                else:
                    # Already have the note, so store the level
                    self.d2 = mb
                    self.NoteOffFn (self.ch, self.cmd, self.d1, self.d2, self.idx)
                    self.d1 = 0
                    self.d2 = 0
            elif (self.cmd == 0x90):
                # Note ON Received
                if (self.d1 == 0):
                    # Store the note number
                    self.d1 = mb
                else:
                    # Already have the note, so store the level
                    self.d2 = mb
                    # Special case if the level (data2) is zero - treat as NoteOff
                    if (self.d2 == 0):
                        self.NoteOffFn (self.ch, self.cmd, self.d1, self.d2, self.idx)
                    else:
                        self.NoteOnFn (self.ch, self.cmd, self.d1, self.d2, self.idx)
                    self.d1 = 0
                    self.d2 = 0
            elif (self.cmd == 0xC0):
                # Program Change
                # This is a single data-byte message
                self.d1 = mb
                self.ThruFn(self.ch, self.cmd, self.d1, -1, self.idx)
                self.d1 = 0
            elif (self.cmd == 0xD0):
                # Channel Pressure
                # This is a single data-byte message
                self.d1 = mb
                self.ThruFn(self.ch, self.cmd, self.d1, -1, self.idx)
                self.d1 = 0
            else:
                # All other commands are two-byte data commands
                
                if (self.d1 == 0):
                    # Store the first data byte
                    self.d1 = mb
                else:
                    # Store the second data byte and action
                    self.d2 = mb
                    self.ThruFn(self.ch, self.cmd, self.d1, self.d2, self.idx)
                    self.d1 = 0
                    self.d2 = 0
                    return True
                    
import machine
import time
import ustruct
from machine import Pin
led = Pin(25, Pin.OUT)


# which MIDI note number corresponds to 0V CV
lowest_note = 40;

# create gate pin
gate = machine.Pin(17, machine.Pin.OUT)
gate.value(0)

#create an I2C bus
sda=machine.Pin(6)
scl=machine.Pin(7)
i2c = machine.I2C(1, scl=scl, sda=sda, freq=400000)
devices = i2c.scan()
if len(devices) != 0:
    print('Number of I2C devices found=',len(devices))
    for device in devices:
        print("Device Hexadecimel Address= ",hex(device))

# calculate 1mV: steps / max V / 1000
mv = 4096 / 5.1 / 1000

# calculate mV per semitone
semitone = 83.33 * mv

# DAC function
def writeToDac(value):
    buf=bytearray(2)
    buf[0]=(value >> 8) & 0xFF
    buf[1]=value & 0xFF
    i2c.writeto(0x60,buf)

# Initialise the serial MIDI handling
uart = machine.UART(0,31250)

# MIDI callback routines
def doMidiNoteOn(ch, cmd, note, vel):
    global semitone
    led.toggle()
    print(f'written {note} {vel} {(int((note-lowest_note)*semitone))}')
    try:
        writeToDac(int((vel-lowest_note)*semitone))
    except Exception as e:
        print(f'write dac failed: {e}')
    gate.value(1)

def doMidiNoteOff(ch, cmd, note, vel):
    global semitone
    gate.value(0)

# initialise MIDI decoder and set up callbacks
md = SimpleMIDIDecoder()
md.cbNoteOn (doMidiNoteOn)
md.cbNoteOff (doMidiNoteOff)
md.cbThru(doMidiNoteOn)

counter = 0
# the loop
while True:
    if counter > 500:
        break    
    # Check for MIDI messages
    if (uart.any()):
        if md.read(uart.read(1)[0]):
            counter += 1
            print(f'counter: {counter}')

