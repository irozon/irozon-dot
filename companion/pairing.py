"""Physical USB enrollment, not an unauthenticated network provisioning endpoint."""
import json
import secrets
import time
from settings import private_ipv4


def ports():
    from serial.tools import list_ports
    return [{'port': p.device, 'description': p.description} for p in list_ports.comports()]


def pair(port, host, pairing_key='', control_token=''):
    import serial
    host = private_ipv4(host)
    if not port or not port.upper().startswith('COM') or not port[3:].isdigit():
        raise ValueError('Select the attached ESP32 COM port')
    pairing_key = pairing_key or secrets.token_hex(32)
    control_token = control_token or secrets.token_hex(32)
    # Set control lines before opening: do not intentionally reset or enter ROM download mode.
    stream = serial.Serial(port=None, baudrate=115200, timeout=.5, write_timeout=2)
    stream.dtr = False
    stream.rts = False
    stream.port = port
    try:
        stream.open()
        stream.reset_input_buffer()
        stream.write(b'{"irozon_probe":1}\n')
        deadline = time.monotonic() + 5
        challenge = None
        while time.monotonic() < deadline:
            raw = stream.readline(512)
            try:
                message = json.loads(raw)
            except (ValueError, UnicodeError):
                continue
            if message.get('irozon_probe') == 1 and isinstance(message.get('nonce'), str):
                challenge = message['nonce']
                break
        if not challenge or len(challenge) != 32:
            raise ValueError('USB pairing unavailable; use compatible firmware and tap RESET to open its pairing window')
        stream.write((json.dumps({'irozon_pair': 1, 'nonce': challenge, 'host': host,
                                  'pairing_key': pairing_key, 'control_token': control_token}) + '\n').encode())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                message = json.loads(stream.readline(512))
            except (ValueError, UnicodeError):
                continue
            if message.get('irozon_pair') == 1 and message.get('accepted') is True:
                return {'pairing_key': pairing_key, 'control_token': control_token}
        raise ValueError('Device did not confirm enrollment; do not assume it was paired')
    finally:
        stream.close()
