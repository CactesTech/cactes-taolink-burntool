




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
                print(f"{x}")
                res = bytes.fromhex(x)[::-1]
                print(f"res: {res.hex()}")
                data += res
    with open(out_file, 'wb') as f:
        f.write(data)

