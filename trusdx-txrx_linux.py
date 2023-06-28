# de SQ3SWF, PE1NNZ 2023
# Modified by toomanycats
# I've removed all the Windows logic forks and all the print statements.
# Also, most of the exceptions have been consolidated into one try/catch block.
# I hope this had sped up the program and made it easier to read.

import pyaudio
import serial
import serial.tools.list_ports
import threading
import time
import os
import datetime
import array
import argparse
from sys import platform

py_audio = pyaudio.PyAudio()

audio_tx_rate_trusdx = 4800
audio_tx_rate = 11520  #11521
audio_rx_rate = 7812
buf = [] # buffer for received audio    
urs = [0] # underrun counter 

# TODO: Make these a dict with nice keyword names.
status = [
          False, # 0 tx_state
          False, # 1 cat_streaming_state
          True,  # 2 running
          False, # 3 cat_active
          False  # 4 keyed_by_rts_dtr
          ]	

virtual_audio_dev_out = '"#"TRUSDX'
virtual_audio_dev_in  = '"#"TRUSDX'
trusdx_serial_dev     = "USB Serial"
loopback_serial_dev   = ""
cat_serial_dev        = ""
alt_cat_serial_dev    = "/tmp/trusdx"

def clean_up(slave1, slave2, ser, ser2):
    print("Stopping")
    time.sleep(1)   
    if slave1:
        os.close(slave1)
    if slave2:
        os.close(slave2)
    if ser2:
        ser2.close()
    try:
        if ser:
            ser.write(b";UA0;")
            ser.close()
    except:
        pass

        py_audio.terminate()

def show_audio_devices():
    for i in range(py_audio.get_device_count()):
        print(py_audio.get_device_info_by_index(i))

    for i in range(py_audio.get_host_api_count()):
        print(py_audio.get_host_api_info_by_index(i))
        
def show_serial_devices():
    for port in serial.tools.list_ports.comports():
        print(port)

def find_serial_device(name, occurance = 0):
    result = [port.device for port in serial.tools.list_ports.comports() if name in port.description]
    # return n-th matching device to name, "" for no match
    if len(result):
        return result[occurance]
    else:
        return ""

def handle_rx_audio(ser, cat, pastream, d):
    # in CAT streaming mode: fwd to audio buf
    if status[1]:
        if status[0] is False:
            buf.append(d)  
        # go to CAT cmd mode when data ends with ';'
        if d[-1] == ord(';'):
            status[1] = False           
    else:
        # go to CAT stream mode when data starts with US
        if d.startswith(b'US'):
            status[1] = True            
        # only send something to cat port, when active
        else:
            if status[3]:               
                cat.write(d)
                cat.flush()

def receive_serial_audio(ser, cat, pastream):
    # rest after ';' that cannot be handled
    bbuf = b''  
    while status[2]:
        # WORKAROUND: special case for TX; this is a workaround to handle CAT responses properly during TX
        if status[0]:  
            if(ser.in_waiting < 1): 
                time.sleep(0.001)
            else:
                d = ser.read()
                handle_rx_audio(ser, cat, pastream, d)

        #normal case for RX
        elif(ser.in_waiting == 0):
            time.sleep(0.001)   

        else:
            d = bbuf + ser.read(ser.in_waiting)
            x = d.split(b';', maxsplit=1)
            cat_delim = (len(x) == 2)
            bbuf = x[1] if cat_delim else b''
            if not cat_delim and len(x[0]) < config['tx_block_size']:
                bbuf = x[0]
                continue
            d = x[0] + b';' if cat_delim else x[0]
            handle_rx_audio(ser, cat, pastream, d)

def play_receive_audio(pastream):
    while status[2]:
        if len(buf) < 2:
            urs[0] += 1
            while len(buf) < 10:
                time.sleep(0.001)

        if not status[0]: 
            pastream.write(buf[0])

        buf.remove(buf[0])

def tx_cat_delay(ser):
    # trusdx TX buffers can be full, empty host buffers (but reset_output_buffer does not seem to work)
    # TODO: consider removing this.
    ser.reset_output_buffer() 
    # trusdx TX buffers can be full, wait until all buffers are empty
    ser.flush()  
    # wait until trusdx buffers are read
    time.sleep(0.0005 + 32/audio_tx_rate_trusdx) 

def handle_cat(pastream, ser, cat):
    if (cat.inWaiting()):
        if status[3] is False:
            status[3] = True

        d = cat.read_until(b";")
        # Workaround for unrealistic fast RTT expectations in hamlib for sequence RX;ID;
        if d.startswith(b'ID'):   
            cat.write(b'ID020;')
            return

        if status[0]:
            tx_cat_delay(ser)
            # in TX mode, interrupt CAT stream by sending ; before issuing CAT cmd 
            ser.write(b";")  
            ser.flush()

        # fwd data on CAT port to trx
        ser.write(d)                
        ser.flush()

        if d.startswith(b"TX"):
           status[0] = True
           pastream.stop_stream()
           pastream.start_stream()
           pastream.read(config['block_size'], exception_on_overflow = False)

        elif d.startswith(b"RX"):
           status[0] = False
           pastream.stop_stream()
           pastream.start_stream()

def transmit_audio_via_serial(pastream, ser, cat):
    while status[2]:
        handle_cat(pastream, ser, cat)

        if status[0] and pastream.get_read_available() > 0:    # in TX mode, and audio available
            samples = pastream.read(config['block_size'], exception_on_overflow = False)
            # array of signed shorts.
            # make this 'H' ??? Was 'h'
            arr = array.array('H', samples)
            # was //512 because with //256 there is 5dB too much signal. Win7 only support 16 bits input audio -> convert to 8 bits
            #samples8 = bytearray([128 + x//256 for x in arr])  
            # filter ; of stream
            #samples8 = samples8.replace(b'\x3b', b'\x3a')      
            arr = arr.replace(b'\x3b', b'\x3a')  
            if status[0]: 
                ser.write(arr)
        else:
            time.sleep(0.001)

def pty_echo(fd1, fd2):
    while status[2]:
        c1 = fd1.read(1)
        fd2.write(c1)

# https://stackoverflow.com/questions/7088672/pyaudio-working-but-spits-out-error-messages-each-time
def run():
    while 1:
        try:
            status[0] = False
            status[1] = False
            status[2] = True
            status[3] = False
            status[4] = False

            # make a tty <-> tty device where one end is opened as serial device, other end by CAT app
            _master1, slave1 = os.openpty()  
            _master2, slave2 = os.openpty()
            master1 = os.fdopen(_master1, 'rb+', 0)
            master2 = os.fdopen(_master2, 'rb+', 0)
            threading.Thread(target=pty_echo, args=(master1,master2)).start()
            threading.Thread(target=pty_echo, args=(master2,master1)).start()
            cat_serial_dev = os.ttyname(slave1)
            loopback_serial_dev = os.ttyname(slave2)

            ser2 = serial.Serial(loopback_serial_dev, 115200, write_timeout = 0)

            in_stream = py_audio.open(frames_per_buffer=0, 
                                              format=pyaudio.paInt16, 
                                              channels=1,
                                              rate=audio_tx_rate,
                                              input=True,
                                              input_device_index=-1)

            out_stream = py_audio.open(frames_per_buffer=0,
                                               format=pyaudio.paUInt8,
                                               channels=1,
                                               rate=audio_rx_rate,
                                               output=True,
                                               output_device_index=-1)
     
            ser = serial.Serial(find_serial_device(trusdx_serial_dev), 115200, write_timeout = 0)

            # wait for device to start after opening serial port
            time.sleep(3) 
            # apply mute
            if config['unmute'] is False:
                cmd = b";MD2;UA1;"
            # unmute
            else:
                cmd = b";MD2;UA2"
            ser.write(cmd)

            threading.Thread(target=receive_serial_audio, args=(ser,ser2,out_stream)).start()
            threading.Thread(target=play_receive_audio, args=(out_stream,)).start()
            threading.Thread(target=transmit_audio_via_serial, args=(in_stream,ser,ser2)).start()

            # can capture this output when scripting auto start.
            print(f"(tr)uSDX driver OK! Available devices = audio_in:{virtual_audio_dev_in}, audio_out:{virtual_audio_dev_out}, cat_port:{cat_serial_dev}" )

            # wait and idle
            while status[2]:    
                time.sleep(1)

        except serial.serialutil.SerialException:
            raise Exception("Rig is not connected to USB port")

        except KeyboardInterrupt:
            self.clean_up(slave1, slave2, ser, ser2)
            
        # Run with faults while waiting for the rig to connect.
        except Exception:
            status[2] = False

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="(tr)uSDX audio driver", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", default=False, help="increase verbosity")
    parser.add_argument("--vox", action="store_true", default=False, help="VOX audio-triggered PTT (Linux only)")
    parser.add_argument("--unmute", action="store_true", default=False, help="Enable (tr)usdx audio")
    parser.add_argument("--direct", action="store_true", default=False, help="Use system audio devices (no loopback)")
    parser.add_argument("--no-rtsdtr", action="store_true", default=False, help="Disable RTS/DTR-triggered PTT")
    parser.add_argument("-B", "--block-size", type=int, default=512, help="RX Block size")
    parser.add_argument("-T", "--tx-block-size", type=int, default=48, help="TX Block size")
    args = parser.parse_args()
    config = vars(args)
    if config['verbose']:
        print(config)

    run()
