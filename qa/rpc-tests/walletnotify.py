#!/usr/bin/env python3
# Copyright (c) 2023 The Dogecoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

#
# Test -walletnotify
#

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import *

class WalletNotifyTest(BitcoinTestFramework):

    def __init__(self):
        super().__init__()
        self.num_nodes = 2
        self.setup_clean_chain = False

    notify_filename = None  # Set by setup_network
    current_line = 0

    def setup_network(self):
        self.nodes = []
        self.notify_filename = os.path.join(self.options.tmpdir, "notify.txt")
        with open(self.notify_filename, 'w', encoding='utf8'):
            pass  # Just open then close to create zero-length file
        self.nodes.append(start_node(0, self.options.tmpdir,
                            ["-walletnotify=echo %s %i >> \"" + self.notify_filename + "\""]))
        self.nodes.append(start_node(1, self.options.tmpdir,[]))
        connect_nodes(self.nodes[1], 0)

        self.is_network_split = False
        self.sync_all()

    def get_notifications(self):
        with open(self.notify_filename, 'r', encoding='utf8') as f:
            notif_text = f.read()
        if len(notif_text) == 0:
            return [];
        return notif_text.split("\n")[:-1] # take out the last entry due to trailing \n

    def run_test(self):
        # Mine 100 blocks from node 1
        self.nodes[1].generate(100)
        self.sync_all()

        # we're going to invalidate this block later: store the hash
        reset_hash = self.nodes[1].getbestblockhash()

        # make sure there are no notifications yet
        assert len(self.get_notifications()) == 0

        # send a tx to node0's wallet
        address = self.nodes[0].getnewaddress()
        txid = self.nodes[1].sendtoaddress(address, 1337)
        self.sync_all()

        # check that we got a notification for the unconfirmed transaction
        notifs = self.get_notifications()
        assert len(notifs) == self.current_line + 1
        assert notifs[self.current_line] == "{} {}".format(txid, 0)
        self.current_line += 1

        # mine a block to confirm the tx
        self.nodes[1].generate(1)
        self.sync_all()

        # check that we got a notification for the confirmed transaction
        height = self.nodes[1].getblockchaininfo()['blocks']
        notifs = self.get_notifications()
        assert len(notifs) == self.current_line + 1
        assert notifs[self.current_line] == "{} {}".format(txid, height)
        self.current_line += 1

        # mine 10 more blocks
        self.nodes[1].generate(10)
        self.sync_all()

        # check that we got a notification for the confirmed transaction
        notifs = self.get_notifications()
        assert len(notifs) == self.current_line

        # rollback the chain and re-mine 30 blocks
        self.nodes[1].invalidateblock(reset_hash)
        self.nodes[1].generate(30)
        sync_blocks(self.nodes)

        # check that we got a notification that the transaction isn't confirmed anymore
        notifs = self.get_notifications()

        #TODO: AS OF RIGHT NOW, THE WALLET WILL SEND 2 NOTIFICATIONS
        #      We need to explain and then fix and/or document this
        #      behavior.

        assert len(notifs) == self.current_line + 2
        assert notifs[self.current_line] == "{} {}".format(txid, 0)
        assert notifs[self.current_line + 1] == "{} {}".format(txid, 0)
        self.current_line += 2

if __name__ == '__main__':
    WalletNotifyTest().main()
