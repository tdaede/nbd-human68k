# human68k-to-fat16 block level translator
# this is only for SCSI disks. floppies are regular fat12
#
# only supports 8.3 names
# does not work with little endian fat disks
# only works with 128MB MO disks currently
# does not support writing (for no good reason)
#
# nbdkit -f -v python nbd-human68k.py file=x68000_midiori_mo.img
# sudo nbd-client localhost /dev/nbd0
# sudo mount -t msdos -o noatime /dev/nbd0 /mnt/floppy

import nbdkit
import errno
import os
import struct
import builtins

class H68K:
    def __init__(self, conf):
        self.fs_offset = 0x8000
        file_size = os.path.getsize(conf["file"])
        self.fs_size = file_size - self.fs_offset
        self.f = builtins.open(conf["file"], 'rb')
        self.f.seek(self.fs_offset)
        x68k_bpb = bytearray(self.f.read(512))
        bytes_per_sector = struct.unpack_from(">H", x68k_bpb, 0x12)[0]
        print("Bytes per sector: ", bytes_per_sector)
        sectors_per_cluster = struct.unpack_from(">B", x68k_bpb, 0x14)[0]
        number_of_fats = struct.unpack_from(">B", x68k_bpb, 0x15)[0]
        reserved_sectors = struct.unpack_from(">H", x68k_bpb, 0x16)[0]
        root_directory_entries = struct.unpack_from(">H", x68k_bpb, 0x18)[0]
        sectors_per_fat = struct.unpack_from(">B", x68k_bpb, 0x1d)[0]
        self.fat_start = bytes_per_sector * reserved_sectors
        self.fat_len = bytes_per_sector * sectors_per_fat * number_of_fats
        self.bpb = bytearray([0x60 ,0x24 ,0x53 ,0x48 ,0x41 ,0x52 ,0x50 ,0x2F ,0x4B ,0x47 ,0x20 ,0x00 ,0x04 ,0x02 ,0x01 ,0x00 ,0x02 ,0x00 ,0x02 ,00 ,00 ,0xF0 ,0x7A ,00 ,00 ,00 ,00 ,00 ,00 ,00 ,00 ,00 ,00 ,0xE4 ,0x01 ,00])

conf = {}

# This just prints the extra command line parameters, but real plugins
# should parse them and reject any unknown parameters.
def config(key, value):
    global conf
    conf[key] = value
    print("ignored parameter %s=%s" % (key, value))


def open(readonly):
    global conf
    h68k = H68K(conf)
    print("open: readonly=%d" % readonly)
    return h68k


def get_size(h68k):
    return h68k.fs_size


def pread(h68k, count, offset):
    b = bytearray()
    for i in range(offset, offset+count):
        if i < 0x24: # replacement bpb
            b.extend(h68k.bpb[i:i+1])
        elif (i >= h68k.fat_start) and (i < (h68k.fat_start + h68k.fat_len)):
            # byteswap fat
            j = i ^ 1
            h68k.f.seek(j + h68k.fs_offset)
            b.extend(bytearray(h68k.f.read(1)))
        else:
            h68k.f.seek(i + h68k.fs_offset)
            b.extend(bytearray(h68k.f.read(1)))
    return b


def pwrite(h, buf, offset):
    pass


def zero(h, count, offset, may_trim):
    global disk
    if may_trim:
        disk[offset:offset+count] = bytearray(count)
    else:
        nbdkit.set_error(errno.EOPNOTSUPP)
        raise Exception
