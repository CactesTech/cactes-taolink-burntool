
from intelhex import IntelHex

def base16_to_bin(in_file, out_file):
    data = b''
    with open(in_file, 'r') as f:
        for line in f:
            data += bytes.fromhex(line)

    with open(out_file, 'wb') as f:
        f.write(data)

def carr_to_bin(in_file, out_file):
    data = b''
    with open(in_file, 'r') as f:
        for line in f:
            if '0x' in line:
                x = line.strip().replace(',', '')[2:]
                # print(f"{x}")
                res = bytes.fromhex(x)[::-1]
                # print(f"res: {res.hex()}")
                data += res
    with open(out_file, 'wb') as f:
        f.write(data)


def intelhex_to_data_array(hex_file_path):
    ih = IntelHex(hex_file_path)

    # Determine the starting and ending addresses
    start_addr = min(ih.addresses())
    end_addr =  max(ih.addresses())

    # Fill the initial part of the array with 0xFF up to the starting address
    data_array = []
    # Append the actual data from the HEX file
    for addr in range(start_addr, end_addr + 1):
        data_array.append(ih[addr])

    return start_addr, end_addr, bytearray(data_array)

def data_array_to_intelhex(hex_file_path, start_address, data):
    # Create an IntelHex object
    ih = IntelHex()

    # Add some data starting at address 0x1000
    for i, byte in enumerate(data):
        ih[start_address + i] = byte

    # Write to a hex file
    ih.write_hex_file(hex_file_path)

def taolink_hex_to_data_array(hex_file_path):
    bin = b''
    with open(hex_file_path, 'r') as f:
        for l in f.readlines():
            h = bytes.fromhex(l)[::-1]
            bin += h

    return 0xC2000000, 0xC2000000 + len(bin), bytearray(bin)

