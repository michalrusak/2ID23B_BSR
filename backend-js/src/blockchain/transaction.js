const zlib = require("zlib");

class Transaction {
  constructor(data, type = "generic") {
    this.data = data;
    this.type = type;
    this.timestamp = Date.now();
    this.crc = this.calculateCRC();
    this.confirmations = new Set();
  }

  calculateCRC() {
    let buf;
    if (Buffer.isBuffer(this.data)) {
      buf = this.data;
    } else if (typeof this.data === "string") {
      buf = Buffer.from(this.data, "utf-8");
    } else {
      buf = Buffer.from(JSON.stringify(this.data));
    }
    return (zlib.crc32 ? zlib.crc32(buf) : require("crc-32").buf(buf))
      .toString(16)
      .padStart(8, "0");
  }

  verifyCRC() {
    return this.crc === this.calculateCRC();
  }

  toDict() {
    return {
      type: this.type,
      data:
        this.type === "image"
          ? Buffer.isBuffer(this.data)
            ? this.data.toString("base64")
            : this.data
          : this.data,
      timestamp: this.timestamp,
      crc: this.crc,
      confirmations: Array.from(this.confirmations),
    };
  }

  static fromDict(obj) {
    let data = obj.data;
    if (obj.type === "image" && typeof data === "string") {
      data = Buffer.from(data, "base64");
    }
    const tx = new Transaction(data, obj.type);
    tx.timestamp = obj.timestamp;
    tx.crc = obj.crc;
    tx.confirmations = new Set(obj.confirmations || []);
    return tx;
  }
}

module.exports = Transaction;
