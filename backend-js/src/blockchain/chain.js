const Block = require("./block");
const Transaction = require("./transaction");
const axios = require("axios");

class BlockchainNode {
  constructor(nodeId, nodes = [], difficulty = 2) {
    this.nodeId = nodeId;
    this.chain = [this.createGenesisBlock()];
    this.difficulty = difficulty;
    this.pendingTransactions = [];
    this.nodes = nodes;
    this.miningStatus = { isMining: false, progress: 0 };
  }

  createGenesisBlock() {
    return new Block(0, "0", [new Transaction("Genesis Block")]);
  }

  getLatestBlock() {
    return this.chain[this.chain.length - 1];
  }

  addTransaction(transaction) {
    if (!transaction.verifyCRC())
      throw new Error("Transaction CRC verification failed");
    this.pendingTransactions.push(transaction);
  }

  async broadcastTransaction(transaction) {
    let confirmations = 1; // self
    for (const node of this.nodes) {
      try {
        const res = await axios.post(
          `${node}/blockchain/verify_transaction`,
          transaction.toDict()
        );
        if (res.status === 200) confirmations++;
      } catch {}
    }
    transaction.confirmations.add(this.nodeId);
    return confirmations >= Math.ceil((this.nodes.length + 1) / 2);
  }

  verifyTransaction(transactionData) {
    const tx = Transaction.fromDict(transactionData);
    if (tx.verifyCRC()) {
      tx.confirmations.add(this.nodeId);
      this.addTransaction(tx);
      return true;
    }
    return false;
  }

  async processImage(imageBuffer) {
    const tx = new Transaction(imageBuffer, "image");
    if (!tx.verifyCRC())
      return { success: false, error: "CRC verification failed" };
    const ok = await this.broadcastTransaction(tx);
    if (!ok) return { success: false, error: "Consensus failed" };
    if (!this.pendingTransactions.includes(tx)) this.addTransaction(tx);
    const miningResult = await this.minePendingTransactions();
    return {
      success: true,
      initial_crc: tx.crc,
      final_crc: tx.crc,
      confirmations: tx.confirmations.size,
      mining_status: miningResult.status,
      mining_message: miningResult.message,
    };
  }

  verifyBlock(block) {
    if (block.index === 0) {
      if (block.previousHash !== "0") return false;
      return block.transactions.every((tx) => tx.verifyCRC());
    }
    if (
      block.hash.substring(0, this.difficulty) !== "0".repeat(this.difficulty)
    )
      return false;
    if (!block.transactions.every((tx) => tx.verifyCRC())) return false;
    return true;
  }

  async minePendingTransactions() {
    if (!this.pendingTransactions.length)
      return {
        success: false,
        message: "No pending transactions",
        status: "idle",
      };
    this.miningStatus.isMining = true;
    const validTxs = this.pendingTransactions.filter(
      (tx) => tx.confirmations.size >= Math.ceil((this.nodes.length + 1) / 2)
    );
    if (!validTxs.length)
      return {
        success: false,
        message: "No transactions with sufficient confirmations",
        status: "waiting_for_confirmations",
      };
    const block = new Block(
      this.chain.length,
      this.getLatestBlock().hash,
      validTxs
    );
    block.mineBlock(this.difficulty);
    // Broadcast mined block
    let confirmations = 1;
    for (const node of this.nodes) {
      try {
        const res = await axios.post(`${node}/blockchain/verify_mined_block`, {
          index: block.index,
          previousHash: block.previousHash,
          timestamp: block.timestamp,
          transactions: block.transactions.map((tx) => tx.toDict()),
          hash: block.hash,
          nonce: block.nonce,
        });
        if (res.status === 200) confirmations++;
      } catch {}
    }
    if (confirmations < Math.ceil((this.nodes.length + 1) / 2)) {
      return {
        success: false,
        message: "Consensus failed",
        status: "consensus_failed",
      };
    }
    this.chain.push(block);
    this.pendingTransactions = this.pendingTransactions.filter(
      (tx) => !validTxs.includes(tx)
    );
    this.miningStatus.isMining = false;
    return {
      success: true,
      message: "Block mined and confirmed",
      status: "completed",
      block: {
        index: block.index,
        hash: block.hash,
        transaction_count: block.transactions.length,
      },
    };
  }

  async initialSync() {
    let longestChain = this.chain;
    for (const node of this.nodes) {
      try {
        const res = await axios.get(`${node}/blockchain/chain`);
        if (res.status === 200 && res.data.length > longestChain.length) {
          const chain = this.reconstructChain(res.data.chain);
          if (chain && this.isChainValid(chain)) longestChain = chain;
        }
      } catch {}
    }
    this.chain = longestChain;
  }

  reconstructChain(chainData) {
    return chainData.map((blockData) => {
      const txs = blockData.transactions.map(Transaction.fromDict);
      const block = new Block(
        blockData.index,
        blockData.previousHash,
        txs,
        blockData.timestamp
      );
      block.hash = blockData.hash;
      block.nonce = blockData.nonce;
      return block;
    });
  }

  isChainValid(chain) {
    for (let i = 1; i < chain.length; i++) {
      const curr = chain[i],
        prev = chain[i - 1];
      if (curr.hash !== curr.calculateHash()) return false;
      if (curr.previousHash !== prev.hash) return false;
      if (
        curr.hash.substring(0, this.difficulty) !== "0".repeat(this.difficulty)
      )
        return false;
      if (!curr.transactions.every((tx) => tx.verifyCRC())) return false;
    }
    return true;
  }

  // ...implement verify_and_correct_hashes, start_hash_verification, verify_and_correct_data, synchronizeNode, resolve_conflicts as needed...
}

module.exports = BlockchainNode;

