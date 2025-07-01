import socket
import struct

class RBCPHeader:
    READ = 0xC0
    WRITE = 0x80

    def __init__(self, rw, id_, data_length, address):
        self.ver_type = 0xFF
        self.cmd_flag = rw & 0xFF
        self.id = id_ & 0xFF
        self.data_length = data_length & 0xFF
        self.address = address & 0xFFFFFFFF

    @classmethod
    def from_bin(cls, data):
        return cls(
            data[1],
            data[2],
            data[3],
            struct.unpack('!I', data[4:8])[0]
        )

    def to_bytes(self):
        return (
            bytes([self.ver_type, self.cmd_flag, self.id, self.data_length])
            + struct.pack('!I', self.address)
        )


class RBCPError(Exception):
    pass


class RBCP:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.id = 0

    def read(self, address, data_length):
        read_data = bytearray()
        while data_length > 0:
            data_length_one_packet = min(data_length, 255)
            dummy_data = b'\x00' * data_length_one_packet  # RBCP requires payload
            read_data.extend(self.com(RBCPHeader.READ, address, data_length_one_packet, dummy_data))
            data_length -= data_length_one_packet
            address += data_length_one_packet
        return read_data
    
    def read8bit(self, address, data_length):
        return list(self.read(address, data_length))

    def read16bit(self, address, data_length):
        return list(struct.unpack('!{}H'.format(data_length), self.read(address, data_length * 2)))

    def read32bit(self, address, data_length):
        return list(struct.unpack('!{}I'.format(data_length), self.read(address, data_length * 4)))

    def write(self, address, data):
        if isinstance(data, int):
            data = [data]
        if isinstance(data, list):
            data = bytes(data)

        remaining_data_length = len(data)
        data_index = 0
        while remaining_data_length > 0:
            data_length_one_packet = min(remaining_data_length, 255)
            data_to_write = data[data_index:data_index + data_length_one_packet]
            self.com(RBCPHeader.WRITE, address + data_index, data_length_one_packet, data_to_write)
            remaining_data_length -= data_length_one_packet
            data_index += data_length_one_packet

    def write8bit(self, address, data):
        self.write(address, data)

    def write16bit(self, address, data):
        if isinstance(data, int):
            data = [data]
        self.write(address, struct.pack('!{}H'.format(len(data)), *data))

    def write32bit(self, address, data):
        if isinstance(data, int):
            data = [data]
        self.write(address, struct.pack('!{}I'.format(len(data)), *data))

    def com(self, rw, address, data_length, data):
        retries = 0
        max_retries = 3
        while retries < max_retries:
            try:
                return self.com_sub(rw, address, data_length, data)
            except RBCPError as e:
                print(e)
                retries += 1
        raise RBCPError("Communication failed after retries")

    def com_sub(self, rw, address, data_length, data):
        print(f"com_sub called: rw={rw}, addr=0x{address:X}, len={data_length}, data={data.hex() if data else None}")

        # Validate input types and values
        assert isinstance(address, int) and 0 <= address <= 0xFFFFFFFF, f"Invalid address: {address}"
        assert isinstance(data_length, int) and 0 < data_length <= 255, f"Invalid data_length: {data_length}"
        assert isinstance(data, (bytes, bytearray)), f"Data must be bytes or bytearray but got {type(data)}"
        assert len(data) == data_length, f"Data length {len(data)} does not match data_length {data_length}"
    
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('0.0.0.0', 0))

            header = RBCPHeader(rw, self.id, data_length, address)
            data_to_be_sent = header.to_bytes() + data

            if sock.sendto(data_to_be_sent, (self.host, self.port)) != len(data_to_be_sent):
                raise RBCPError("Cannot send data")

            sock.settimeout(1)
            try:
                received_data, _ = sock.recvfrom(255 + 8)
            except socket.timeout:
                raise RBCPError("Timeout")

            self.validate(rw, address, data_length, data, received_data)
            self.id = (self.id + 1) & 0xFF
            return received_data[8:]

    def validate(self, rw, address, data_length, data, received_data):
        header = RBCPHeader.from_bin(received_data)
        if received_data[0] != 0xFF:
            raise RBCPError("Invalid Ver Type")
        if header.cmd_flag != (rw | 0x08):
            if header.cmd_flag & 0x01:
                raise RBCPError("Bus Error")
            else:
                raise RBCPError("Invalid CMD Flag")
        if header.id != self.id:
            raise RBCPError("Invalid ID")
        if header.data_length != data_length:
            raise RBCPError("Invalid DataLength")
        if header.address != address:
            raise RBCPError("Invalid Address")
        if header.data_length != len(received_data) - 8:
            raise RBCPError("Frame Error")
