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
    notifs = []

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

    def wait_for_notifications(self, num, exact):
        notifs = self.notifs
        expected = self.current_line + num
        def notifications_received(self):
            notifs = self.get_notifications()
            if exact:
                return len(notifs) == expected
            return len(notifs) >= expected
        if wait_until(notifications_received, timeout=20):
            self.notifs = notifs
            return True
        return False

    def run_test(self):
        # Mine 60 blocks from node 1
        self.nodes[1].generate(60)
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
        assert self.wait_for_notifications(1, True)
        assert self.notifs[self.current_line] == "{} {}".format(txid, 0)
        assert self.nodes[0].gettransaction(txid)['confirmations'] == 0
        self.current_line += 1


        # mine a block to confirm the tx
        self.nodes[1].generate(1)
        self.sync_all()

        # check that we got a notification for the confirmed transaction
        assert self.wait_for_notifications(1, True)
        height = self.nodes[1].getblockchaininfo()['blocks']
        assert self.notifs[self.current_line] == "{} {}".format(txid, height)
        assert self.nodes[0].gettransaction(txid)['confirmations'] == 1
        self.current_line += 1

        # mine 10 more blocks
        self.nodes[1].generate(10)
        self.sync_all()

        # check that we got no more notifications
        assert self.wait_for_notifications(0, True)
        assert self.nodes[0].gettransaction(txid)['confirmations'] == 11

        # rollback the chain and re-mine 30 blocks
        self.nodes[1].invalidateblock(reset_hash)
        self.nodes[1].generate(30)
        sync_blocks(self.nodes)

        # we should now receive 2 notifications:
        # - from the transaction being put into the mempool (AcceptToMemoryPool)
        # - from the transaction no longer being in the best chain (DisconnectTip)
        #
        # The order depends on how far the rollback goes; in our case the above
        # order reflects the respective triggers for the notifications, because
        # we roll back before the block that mined the tx. If we were to stop
        # rolling back at exactly the block that mined the tx, the order would
        # be reversed.
        #
        # In rare occasions, the reversed transaction is included in one of the
        # 30 new blocks we mined, so don't wait for exactly 2 notifications, as
        # there may be 3.
        assert self.wait_for_notifications(2, False)
        assert self.notifs[self.current_line] == "{} {}".format(txid, 0)
        assert self.notifs[self.current_line + 1] == "{} {}".format(txid, 0)
        assert self.nodes[0].gettransaction(txid)['confirmations'] == 0
        self.current_line += 2

        # mine the same transaction again and make sure it's in the mempool by
        # force submitting it on the miner node.
        self.nodes[1].sendrawtransaction(self.nodes[0].gettransaction(txid)['hex'], True)
        self.nodes[1].generate(1)
        self.sync_all()

        # we should now have received one more notification.
        assert self.wait_for_notifications(1, True)
        height = self.nodes[1].getblockchaininfo()['blocks']
        assert self.notifs[self.current_line] == "{} {}".format(txid, height)
        assert self.nodes[0].gettransaction(txid)['confirmations'] == 1
        self.current_line += 1




if __name__ == '__main__':
    WalletNotifyTest().main()
