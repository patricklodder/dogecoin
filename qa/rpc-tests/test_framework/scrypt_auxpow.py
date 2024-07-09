#!/usr/bin/env python
# Copyright (c) 2014 Daniel Kraft
# Copyright (c) 2015-2022 The Dogecoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

# General code for scrypt auxpow testing.  This includes routines to
# solve an auxpow header and to generate auxpow blocks with scrypt.
# extends and modifies auxpow module by Daniel Kraft.

# This module requires a built and installed version of the ltc_scrypt
# package, which can be downloaded from:
# https://pypi.python.org/packages/source/l/ltc_scrypt/ltc_scrypt-1.0.tar.gz

from .auxpow import *
from .mininode import (
    CBlock, CBlockHeader, CTransaction, CTxIn, CTxOut,
    COutPoint, ser_uint256, ser_string, uint256_from_compact,
)
from .script import CScript
import ltc_scrypt
import binascii

def computeAuxpowWithChainId (block, target, chainid, ok):
  """
  Build an auxpow object (serialised as hex string) that solves the
  block, for a given chain id.
  """

  # Start by building the merge-mining coinbase.  The merkle tree
  # consists only of the block hash as root.
  coinbase = "fabe" + binascii.hexlify((b"m" * 2)).decode("ascii")
  coinbase += block
  coinbase += "01000000" + ("00" * 4)

  # Construct "vector" of transaction inputs.
  vin = "01"
  vin += ("00" * 32) + ("ff" * 4)
  vin += ("%02x" % int(len (coinbase) / 2)) + coinbase
  vin += ("ff" * 4)

  # Build up the full coinbase transaction.  It consists only
  # of the input and has no outputs.
  tx = "01000000" + vin + "00" + ("00" * 4)
  txHash = doubleHashHex (tx)

  # Construct the parent block header.  It need not be valid, just good
  # enough for auxpow purposes.
  header = "0100" + chainid + "00"
  header += "00" * 32
  header += reverseHex (txHash)
  header += "00" * 4
  header += "00" * 4
  header += "00" * 4

  # Mine the block.
  (header, blockhash) = mineScryptBlock (header, target, ok)

  # Build the MerkleTx part of the auxpow.
  output = tx
  output += blockhash
  output += "00"
  output += "00" * 4

  # Extend to full auxpow.
  output += "00"
  output += "00" * 4
  output += header

  return output

# for now, just offer hashes to rpc until it matches the work we need
def mineScryptAux (node, chainid, ok):
  """
  Mine an auxpow block on the given RPC connection.
  """

  auxblock = node.getauxblock ()
  target = reverseHex (auxblock['target'])

  apow = computeAuxpowWithChainId (auxblock['hash'], target, chainid, ok)
  res = node.getauxblock (auxblock['hash'], apow)
  return res

def mineSimpleEmptyAuxBlock(version, time, prevBlock, target, coinbasetx, ok=True):
    # Construct the auxpow proven block
    block = CAuxpowBlock()
    block.nVersion = version
    block.nTime = time
    block.hashPrevBlock = prevBlock
    block.nBits = target
    block.vtx.append(coinbasetx)
    block.hashMerkleRoot = block.calc_merkle_root()
    block.calc_sha256()

    # now that we have a hash, create the parent coinbase
    mm_coinbase = struct.pack("<I", 0xfabe) + (b"m" * 2) + ser_uint256(block.sha256)
    parent_coinbasetx = CTransaction()
    parent_coinbasetx.vin.append(CTxIn(COutPoint(0, 0xffffffff), ser_string(mm_coinbase)), 0xffffffff)
    parent_coinbasetx.vout.append(CTxOut(0, CScript([OP_TRUE])))
    parent_coinbasetx.calc_sha256()

    # create the parent block
    parent_block = CBlock()
    parent_block.nTime = time
    parent_block.nBits = target
    parent_block.vtx.append(parent_coinbasetx)
    parent_block.hashMerkleRoot = parent_block.calc_merkle_root()

    # mine the parent block
    parent_blockhdr = mineScryptHeader(parent_block, target, ok)

    # create auxdata - we can leave all the merkle branches empty in this case
    auxdata = CAuxData()
    auxdata.tx = parent_coinbasetx
    auxdata.parent_blockhdr = parent_blockhdr
    block.auxdata = auxdata

    return block

def mineScryptHeader(header, bits, ok):
    """Mine a CBlockHeader with scrypt"""
    target = uint256_from_compact(bits)
    while True:
        header.nNonce += 1
        header.calc_sha256() #TODO: may want to fix in mininode - bit of a misnomer
        if (ok and header.scrypt256 < target) or ((not ok) and header.scrypt256 > target):
            break
    return CBlockHeader(header)

def mineScryptBlock (header, target, ok):
  """
  Given a block header, update the nonce until it is ok (or not)
  for the given target.
  """

  data = bytearray (binascii.unhexlify(header))
  while True:
    assert data[79] < 255
    data[79] += 1
    hexData = binascii.hexlify(data).decode("ascii")

    scrypt = getScryptPoW(hexData)
    if (ok and scrypt < target) or ((not ok) and scrypt > target):
      break

  blockhash = doubleHashHex (hexData)
  return (hexData, blockhash)

def getScryptPoW(hexData):
  """
  Actual scrypt pow calculation
  """

  data = binascii.unhexlify(hexData)

  return reverseHex(binascii.hexlify(ltc_scrypt.getPoWHash(data)).decode("ascii"))
