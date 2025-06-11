const crypto = require("crypto");

class Block {
  constructor(index, previousHash, transactions, timestamp = Date.now()) {
    this.index = index;
    this.previousHash = previousHash;
    this.transactions = transactions;
    this.timestamp = timestamp;
    this.nonce = 0;
    this.hash = this.calculateHash();
  }

  calculateHash() {
    return crypto
      .createHash("sha256")
      .update(
        this.index +
          this.previousHash +
          JSON.stringify(this.transactions.map((tx) => tx.toDict())) +
          this.timestamp +
          this.nonce
      )
      .digest("hex");
  }

  mineBlock(difficulty) {
    const target = Array(difficulty + 1).join("0");
    while (this.hash.substring(0, difficulty) !== target) {
      this.nonce++;
      this.hash = this.calculateHash();
    }
  }
}

module.exports = Block;

