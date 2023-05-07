#!/usr/bin/env python3
# de SQ3SWF 2023
#
#Linux:
#stty -F /dev/ttyUSB0 raw -echo -echoe -echoctl -echoke -hupcl 115200;
#socat -d -d pty,link=/tmp/ttyS0,echo=0,ignoreeof,b115200,raw,perm=0777 pty,link=/tmp/ttyS1,echo=0,ignoreeof,b115200,raw,perm=0777 &
#pactl load-module module-null-sink sink_name=TRUSDX sink_properties=device.description="TRUSDX"
#pavucontrol
####
#sudo modprobe snd-aloop
#
# Windows 7:
# Install python3.6
# python -m pip install --upgrade pip
# python -m pip install pyaudio   # or download and install the matching version from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
# python -m pip install pyaudio
# Install, extract VB-Audio Virtual Audio Cable from https://download.vb-audio.com/
# Install VB-Audio by clicking right on x64 executable and select Run as Administrator, click install driver
# Download and extract com0com from https://sourceforge.net/projects/com0com/
# setup.exe /S /D=C:\Program Files\com0com
# Install x64 executable. In case of driver-signing issues: every-time reboot Windows by holding F8 (Win7) or Shift (Win8/10), select "Disable Driver Signature Enforcement" in Advanced Boot options
# Select Start > com0com > Setup Command Prompt, and enter: uninstall > enter: install PortName=COM8 PortName=COM9
# or open Command Prompt > cd C:\Program Files (x86)\com0com > setupc install PortName=COM8 PortName=COM9
# Select CABLE audio devices and COM8 in WSJT-X or any other HAM radio program

# Build: sudo apt install patchelf && python -m pip install -U nuitka
# python -m nuitka --standalone trusdx-txrx.py

# Setup_com0com_v3.0.0.0_W7_x64_signed.exe  /S /D=C:\Program Files\com0com
# cd "c:\Program Files\com0com"
# setupc.exe install PortName=COM8 PortName=COM9
# (as admin) VBCABLE_Setup_x64.exe

#
# Linux:
# sudo apt install portaudio19-dev

import pyaudio
import serial
import serial.tools.list_ports
import threading
import time
import os
import datetime
import array

## change these (if you need to)
audio_tx_rate = 11521
audio_rx_rate = 7812
trusdx_mute = True
vox_mode = False
debug = True

from sys import platform
if platform == "linux" or platform == "linux2":
    virtual_audio_dev_out = ""#"Loopback"#"TRUSDX"
    virtual_audio_dev_in  = ""#"Loopback"#"TRUSDX"
    trusdx_serial_dev     = "USB Serial"
    loopback_serial_dev   = "/tmp/ttyS1"
elif platform == "win32":
    virtual_audio_dev_out = "CABLE Output"
    virtual_audio_dev_in  = "CABLE Input"
    trusdx_serial_dev     = "CH340"
    #loopback_serial_dev   = "com0com"
    loopback_serial_dev   = "COM9"
elif platform == "darwin":
    print("TBD")
    # OS X
## 

buf = []    # buffer for received audio
urs = [0]   # underrun counter
status = [False, False]	# tx_state, cat_streaming_state
chunksize = 512

def log(msg):
    if(debug): print(f"{datetime.datetime.utcnow()} {msg}")

def show_audio_devices():
    for i in range(pyaudio.PyAudio().get_device_count()):
        print(pyaudio.PyAudio().get_device_info_by_index(i))
    for i in range(pyaudio.PyAudio().get_host_api_count()):
        print(pyaudio.PyAudio().get_host_api_info_by_index(i))
def find_audio_device(name, occurance = 0):
    if platform == "linux" or platform == "linux2": return -1  # not supported
    result = [i for i in range(pyaudio.PyAudio().get_device_count()) if name in (pyaudio.PyAudio().get_device_info_by_index(i)['name']) ]
    return result[occurance] if len(result) else -1 # return n-th matching device to name, -1 for no match

def show_serial_devices():
    for port in serial.tools.list_ports.comports():
        print(port)

def find_serial_device(name, occurance = 0):
    result = [port.device for port in serial.tools.list_ports.comports() if name in port.description]
    return result[occurance] if len(result) else "" # return n-th matching device to name, "" for no match

def receive_serial_audio(serport, catport):
    while True:
        d = serport.read_until(b";", chunksize)   # read until CAT end or enough in buf
        if status[1]:
            #log(f"stream: {d}")
            buf.append(d)                   # in CAT streaming mode: fwd to audio buf
            if d[-1] == ord(';'):
                status[1] = False           # go to CAT cmd mode when data ends with ';'
                #log("***CAT mode")
        else:
            if d.startswith(b'US'):
                #log("***US mode")
                status[1] = True            # go to CAT stream mode when data starts with US
            else:
                catport.write(d)
                catport.flush()
                log(f"O: {d}")  # in CAT command mode

def play_receive_audio(pastream):
    while True:
        if len(buf) < 2:
            #log(f"UNDERRUN #{urs[0]} - refilling")
            urs[0] += 1
            while len(buf) < 10:
                time.sleep(0.01)
        if not status[0]: pastream.write(buf[0])
        buf.remove(buf[0])

def transmit_audio_via_serial_vox(pastream, serport, catport):
    log("transmit_audio_via_serial_vox")
    while True:
        samples = pastream.read(chunksize, exception_on_overflow = False)
        samplesa = array.array('h', samples)
        samples8 = bytearray([128 + x//512 for x in samplesa])  # Win7 only support 16 bits input audio -> convert to 8 bits
        #log(f"{128 - min(samples8)} {max(samples8) - 127}")
        if (128 - min(samples8)) == 64 and (max(samples8) - 127) == 64: # if does contain very loud signal
            if not status[0]:
                status[0] = True
                log("TX ON")
                serport.write(b"UA2;TX0;")
            if status[0]:
                serport.write(samples8)
        elif status[0]:  # in TX and no audio detected (silence)
            time.sleep(0.1)
            serport.write(b";RX;")
            status[0] = False
            log("TX OFF")

def forward_cat(pastream, serport, catport):
    if(catport.inWaiting()):
        d = catport.read_until(b";")
        if True and d.startswith(b'ID'):   # this is a workaround for unrealistic fast RTT expectations in hamlib for sequence RX;ID;
            catport.write(b'ID020;')
            log(f"I: {d}")
            log(f"O: ID020; (emu)")
            #serport.write(b";UA2;" if trusdx_mute else b";UA1;")     # instead issue UA cmd to keep rig in streaming mode
            return
        if status[0]:
            #log("***;")
            serport.flush()  # because trusdx TX buffers can be full, wait until all buffers are empty
            time.sleep(0.01) # and wait a bit before intteruptin TX stream for a CAT cmd
            serport.write(b";")  # in TX mode, interrupt CAT stream by sending ; before issuing CAT cmd
        log(f"I: {d}")
        serport.write(d)                # fwd data on CAT port to trx
        serport.flush()
        if d.startswith(b"TX"):
           status[0] = True
           #log("***TX mode")
           pastream.stop_stream()
           pastream.start_stream()
           pastream.read(chunksize, exception_on_overflow = False)
        if d.startswith(b"RX"):
           status[0] = False
           #log("***RX mode")

def transmit_audio_via_serial_cat(pastream, serport, catport):
    log("transmit_audio_via_serial_cat")
    while True:
        forward_cat(pastream, serport, catport)
        if status[0] and pastream.get_read_available() > 0:    # in TX mode, and audio available
            samples = pastream.read(chunksize, exception_on_overflow = False)
            if status[0]:
               arr = array.array('h', samples)
               samples8 = bytearray([128 + x//512 for x in arr])  # Win7 only support 16 bits input audio -> convert to 8 bits
               samples8 = samples8.replace(b'\x3b', b'\x3a')      # filter ; of stream
               serport.write(samples8)
        else:
            time.sleep(0.001)

def main():
    show_audio_devices()
    print("Audio device = ", find_audio_device(virtual_audio_dev_in), find_audio_device(virtual_audio_dev_out) )
    show_serial_devices()
    print("Serial device = ", find_serial_device(trusdx_serial_dev) )
    print("Serial loopback = ", find_serial_device(loopback_serial_dev) )

    #   master, slave = os.openpty()
    #   print(os.ttyname(slave))
    #   ser2 = serial.Serial(os.ttyname(master), 115200, write_timeout = 0)
    ser2 = serial.Serial(loopback_serial_dev, 115200, write_timeout = 0)
    #    ser2 = serial.Serial(find_serial_device(loopback_serial_dev), 115200, write_timeout = 0)

    ser = serial.Serial(find_serial_device(trusdx_serial_dev), 115200, write_timeout = 0)
    #ser.dtr = True
    #ser.rts = False
    #ser2.dtr = True
    #ser2.rts = False

    time.sleep(3) # wait for device to start after opening serial port
    ser.write(b";UA2;" if trusdx_mute else b";UA1;") # enable audio streaming, mute trusdx

    in_stream = pyaudio.PyAudio().open(frames_per_buffer=0, format = pyaudio.paInt16, channels = 1, rate = audio_tx_rate, input = True, input_device_index = find_audio_device(virtual_audio_dev_out) if virtual_audio_dev_out else -1)
    out_stream = pyaudio.PyAudio().open(frames_per_buffer=0, format = pyaudio.paUInt8, channels = 1, rate = audio_rx_rate, output = True, output_device_index = find_audio_device(virtual_audio_dev_in) if virtual_audio_dev_in else -1)

    threading.Thread(target=receive_serial_audio, args=(ser,ser2)).start()
    threading.Thread(target=play_receive_audio, args=(out_stream,)).start()
    threading.Thread(target=transmit_audio_via_serial_vox if vox_mode else transmit_audio_via_serial_cat, args=(in_stream,ser,ser2)).start()

    # display some stats every 10 seconds
    ts = time.time()
    while 1:
        #log(f"{int(time.time()-ts)} buf: {len(buf)}")
        time.sleep(10)

if __name__ == '__main__':
    #try:
        main()
    #except Exception as e:
    #    print(f"Error: {e}")
    #    time.sleep(3)
