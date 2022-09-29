#!/usr/bin/env python3
# Copyright (c) 2018-2020 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Wallet regression test

Test whether wallets from older versions can be imported by the current
software without warnings.

The following needs to be ran prior to executing this test:

test/get_previous_releases.py -b v1.14.0 v1.14.2 v1.14.4 v1.14.6

"""

import os
import shutil
from pathlib import Path

from test_framework.test_framework import BitcoinTestFramework
from test_framework.descriptors import descsum_create

from test_framework.util import (
    assert_equal,
    assert_raises_rpc_error,
)


class WalletRegressionTest(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 6
        # Add new version whenever changes to wallets were made in a new release
        self.extra_args = [
            [], # Current code: use to mine blocks
            [], # Current code: use to receive coins, swap wallets, etc
            [], # v1.14.0
            [], # v1.14.2
            [], # v1.14.4
            [], # v1.14.6
        ]
        self.wallet_names = [self.default_wallet_name]

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()
        self.skip_if_no_previous_releases()

    def setup_nodes(self):
        self.add_nodes(self.num_nodes, extra_args=self.extra_args, versions=[
            None,
            None,
            1140000,
            1140200,
            1140400,
            1140600,
        ])

        self.start_nodes()
        self.import_deterministic_coinbase_privkeys()

    def run_test(self):
        # note: on 1.21-dev, coinbase maturity is set to 240, whereas before
        # it was 60. Until that is harmonized, regtest can fork, but not if
        # we simply do the mining on 1.21 nodes only for now.
        self.nodes[0].generatetoaddress(241, self.nodes[0].getnewaddress())

        self.sync_blocks()

        # Sanity check the test framework:
        res = self.nodes[self.num_nodes - 1].getblockchaininfo()
        assert_equal(res['blocks'], 241)

        # alias all other nodes
        node_master = self.nodes[self.num_nodes - 5]
        node_v1400 = self.nodes[self.num_nodes - 4]
        node_v1402 = self.nodes[self.num_nodes - 3]
        node_v1404 = self.nodes[self.num_nodes - 2]
        node_v1406 = self.nodes[self.num_nodes - 1]

        # prepare backup directories for later
        for n in [node_v1400, node_v1402, node_v1404, node_v1406]:
            Path(os.path.join(n.datadir, "regtest", "backups")).mkdir(exist_ok=True)

        self.log.info("Test wallet import")
        # Send money to each wallet version we test
        self.nodes[0].sendtoaddress(node_v1400.getnewaddress(), 1400)
        self.nodes[0].sendtoaddress(node_v1402.getnewaddress(), 1402)
        self.nodes[0].sendtoaddress(node_v1404.getnewaddress(), 1404)
        self.nodes[0].sendtoaddress(node_v1406.getnewaddress(), 1406)

        # mine a block
        self.nodes[0].generatetoaddress(1, self.nodes[0].getnewaddress())
        self.sync_blocks()

        assert node_v1400.getwalletinfo()['balance'] == 1400
        assert node_v1402.getwalletinfo()['balance'] == 1402
        assert node_v1404.getwalletinfo()['balance'] == 1404
        assert node_v1406.getwalletinfo()['balance'] == 1406

        # construct wallet paths
        node_master_wallets_dir = os.path.join(node_master.datadir, "regtest", "wallets")

        v1400_wallet = os.path.join(node_v1400.datadir, "regtest", "backups", "wallet.dat")
        v1402_wallet = os.path.join(node_v1402.datadir, "regtest", "backups", "wallet.dat")
        v1404_wallet = os.path.join(node_v1404.datadir, "regtest", "backups", "wallet.dat")
        v1406_wallet = os.path.join(node_v1406.datadir, "regtest", "backups", "wallet.dat")

        # backup the wallets
        node_v1400.backupwallet(v1400_wallet)
        node_v1402.backupwallet(v1402_wallet)
        node_v1404.backupwallet(v1404_wallet)
        node_v1406.backupwallet(v1406_wallet)

        # copy wallets
        shutil.copyfile(
            v1400_wallet,
            os.path.join(node_master_wallets_dir, 'wallet_1400.dat')
        )
        shutil.copyfile(
            v1402_wallet,
            os.path.join(node_master_wallets_dir, 'wallet_1402.dat')
        )
        shutil.copyfile(
            v1404_wallet,
            os.path.join(node_master_wallets_dir, 'wallet_1404.dat')
        )
        shutil.copyfile(
            v1406_wallet,
            os.path.join(node_master_wallets_dir, 'wallet_1406.dat')
        )

        # import each wallet
        for w in ["wallet_1400.dat", "wallet_1402.dat", "wallet_1404.dat", "wallet_1406.dat"]:
            # make sure that we don't get any warnings about the derivation path
            with node_master.assert_debug_log(
                expected_msgs=['Loading wallet'],
                unexpected_msgs=['Unexpected path index']
            ):
                node_master.loadwallet(w)

            # make sure the moneys are there
            wallet = node_master.get_wallet_rpc(w)
            balance = wallet.getwalletinfo()['balance']
            assert balance > 1399
            self.log.info(f'{w}: {balance}')


if __name__ == '__main__':
    WalletRegressionTest().main()
