#!/usr/bin/env python3
# Copyright (c) 2014 Daniel Kraft
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

# General code for auxpow testing.  This includes routines to
# solve an auxpow and to generate auxpow blocks.

import binascii
import hashlib
from .mininode import (
    CBlockHeader, CBlock, CTransaction, deser_uint256_vector, deser_uint256,
    ser_uint256, ser_uint256_vector, deser_vector
)

class CAuxData(object):
    def __init__(self, auxdata=None):
        if auxdata is None:
            self.tx = None
            self.blockhash = None
            self.index = 0
            self.merkle_branch = []
            self.chain_index = 0
            self.chain_merkle_branch = []
            self.parent_blockhdr = None
        else:
            self.tx = auxdata.tx
            self.blockhash = auxdata.blockhash
            self.index = auxdata.index
            self.merkle_branch = auxdata.merkleBranch
            self.chain_index = auxdata.chainIndex
            self.chain_merkle_branch = auxdata.chainMerkleBranch
            self.parent_blockhdr = auxdata.parentBlock

    def deserialize(self, f):
        self.tx = CTransaction()
        self.tx.deserialize(f)
        self.blockhash = deser_uint256(f)
        self.index = struct.unpack("<I", f.read(4))[0]
        self.merkle_branch = deser_uint256_vector(f)
        self.chain_index = struct.unpack("<I", f.read(4))[0]
        self.chain_merkle_branch = deser_uint256_vector(f)
        self.parent_blockhdr = CBlockHeader()
        self.parent_blockhdr.deserialize(f)

    def serialize(self):
        r = b""
        r += self.tx.serialize()
        r += ser_uint256(self.blockhash)
        r += struct.pack("<I", self.index)
        r += ser_uint256_vector(self.merkle_branch)
        r += struct.pack("<I", self.chain_index)
        r += ser_uint256_vector(self.chain_merkle_branch)
        r += self.parent_blockhdr.serialize()
        return r

class CAuxpowBlock(CBlock):
    def __init__(self, header=None, auxdata=None):
        super(CBlock, self).__init__(header)
        if self.is_auxpow():
            assert auxdata is not None
            self.auxdata = CAuxData(auxdata)

    def is_auxpow(self):
        return (self.version & 0xffff0000 == 0x0062) and (self.version & 0x000001000 == 0x0100)

    def deserialize(self, f):
        CBlockHeader.deserialize(self, f)
        if self.is_auxpow():
            self.auxdata = CAuxData()
            self.auxdata.deserialize(f)
        self.vtx = deser_vector(f, CTransaction)

    def serialize(self):
        r = b""
        r += CBlockHeader.deserialize(self)
        if self.is_auxpow():
            r += self.auxdata.deserialize()
        r += ser_vector(self.vtx)
        return r


def computeAuxpow (block, target, ok):
  """
  Build an auxpow object (serialised as hex string) that solves
  (ok = True) or doesn't solve (ok = False) the block.
  """

  # Start by building the merge-mining coinbase.  The merkle tree
  # consists only of the block hash as root.
  coinbase = "fabe" + binascii.hexlify("m" * 2)
  coinbase += block
  coinbase += "01000000" + ("00" * 4)

  # Construct "vector" of transaction inputs.
  vin = "01"
  vin += ("00" * 32) + ("ff" * 4)
  vin += ("%02x" % (len (coinbase) / 2)) + coinbase
  vin += ("ff" * 4)

  # Build up the full coinbase transaction.  It consists only
  # of the input and has no outputs.
  tx = "01000000" + vin + "00" + ("00" * 4)
  txHash = doubleHashHex (tx)

  # Construct the parent block header.  It need not be valid, just good
  # enough for auxpow purposes.
  header = "01000000"
  header += "00" * 32
  header += reverseHex (txHash)
  header += "00" * 4
  header += "00" * 4
  header += "00" * 4

  # Mine the block.
  (header, blockhash) = mineBlock (header, target, ok)

  # Build the MerkleTx part of the auxpow.
  auxpow = tx
  auxpow += blockhash
  auxpow += "00"
  auxpow += "00" * 4

  # Extend to full auxpow.
  auxpow += "00"
  auxpow += "00" * 4
  auxpow += header

  return auxpow

def mineAuxpowBlock (node):
  """
  Mine an auxpow block on the given RPC connection.
  """

  auxblock = node.getauxblock ()
  target = reverseHex (auxblock['target'])
  apow = computeAuxpow (auxblock['hash'], target, True)
  res = node.getauxblock (auxblock['hash'], apow)
  assert res

def mineBlock (header, target, ok):
  """
  Given a block header, update the nonce until it is ok (or not)
  for the given target.
  """

  data = bytearray (binascii.unhexlify (header))
  while True:
    assert data[79] < 255
    data[79] += 1
    hexData = binascii.hexlify (data)

    blockhash = doubleHashHex (hexData)
    if (ok and blockhash < target) or ((not ok) and blockhash > target):
      break

  return (hexData, blockhash)

def doubleHashHex (data):
  """
  Perform Bitcoin's Double-SHA256 hash on the given hex string.
  """

  hasher = hashlib.sha256 ()
  hasher.update (binascii.unhexlify (data))
  data = hasher.digest ()

  hasher = hashlib.sha256 ()
  hasher.update (data)

  return reverseHex (hasher.hexdigest ())

def reverseHex (data):
  """
  Flip byte order in the given data (hex string).
  """

  b = bytearray (binascii.unhexlify(data))
  b.reverse ()

  return binascii.hexlify(b).decode("ascii")
