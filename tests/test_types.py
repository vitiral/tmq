from unittest import TestCase

from tmq import define as td


class TestHash(TestCase):
    def test_short(self):
        result = td.tmq_hash("short hash")
        self.assertEqual(result, 0x20dc540e)

    def test_long(self):
        result = td.tmq_hash("this is a pretty long hash string")
        self.assertEqual(result, 0xb4c660d0)


class TestPacket(TestCase):
    def test_pack_unpack(self):
        packet = (0x55, (0x4567, 0xF0F0, 0x4444), b'This is a bunch of data')
        packed = td.tmq_pack(*packet)
        result = td.tmq_unpack(packed)
        self.assertEqual(result, packet)


class TestAddresses(TestCase):
    def test_pack_unpack(self):
        address = ('127.0.0.1', 42)
        packed = td.tmq_pack_address_t(*address)
        result, *_ = td.tmq_unpack_address_t(packed)
        expected = tuple(int(a) for a in address[0].split('.')), address[1]
        self.assertEqual(result, expected)

    def test_pack_unpack_several(self):
        addresses = [((127, 0, 0, 1), 42),
                     ((127, 0, 0, 1), 142),
                     ((192, 142, 0, 1), 67),
                     ((8, 8, 8, 8), 80),
                     ]
        packed = td.tmq_pack_addresses(addresses)
        result = td.tmq_unpack_addresses(packed)
        self.assertEqual(result, addresses)

