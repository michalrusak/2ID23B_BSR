const express = require("express");
const bodyParser = require("body-parser");
const path = require("path");
const config = require("config");
const fs = require("fs").promises;
const apiRoutes = require("./api/routes");
const tracker = require("./torrent/tracker");
const seeder = require("./torrent/seeder");
const multer = require("multer");
const BlockchainNode = require("./blockchain/chain");
const Transaction = require("./blockchain/transaction");
const Block = require("./blockchain/block");
const cors = require("cors");
const dotenv = require("dotenv");

dotenv.config();

const userRouter = require("./user/user");

const upload = multer();

class Server {
  constructor() {
    this.app = express();
    this.port = process.env.PORT || config.get("api.port") || 3000;
    this.init();
  }

  async init() {
    await this.setupDirectories();
    this.setupMiddlewares();
    this.setupRoutes();
  }

  async setupDirectories() {
    // Upewnij się, że wszystkie katalogi istnieją
    const directories = [
      config.get("storage.imagesPath"),
      config.get("storage.torrentsPath"),
      config.get("storage.temporaryPath"),
    ];

    for (const dir of directories) {
      try {
        await fs.mkdir(dir, { recursive: true });
        console.log(`Directory created or already exists: ${dir}`);
      } catch (error) {
        console.error(`Error creating directory ${dir}: ${error.message}`);
      }
    }
  }

  setupMiddlewares() {
    // Konfiguracja parsera JSON z większym limitem dla obrazów
    this.app.use(bodyParser.json({ limit: "50mb" }));
    this.app.use(bodyParser.urlencoded({ extended: true, limit: "50mb" }));

    // Middleware do logowania żądań
    this.app.use((req, res, next) => {
      console.log(`${new Date().toISOString()} - ${req.method} ${req.url}`);
      next();
    });

    // Middleware do obsługi błędów CORS
    this.app.use((req, res, next) => {
      res.header("Access-Control-Allow-Origin", "*");
      res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE");
      res.header("Access-Control-Allow-Headers", "Content-Type, Authorization");

      if (req.method === "OPTIONS") {
        return res.sendStatus(200);
      }
      next();
    });

    // Middleware do statycznych plików
    this.app.use(
      "/files",
      express.static(path.join(process.cwd(), config.get("storage.imagesPath")))
    );
    this.app.use(
      "/torrents",
      express.static(
        path.join(process.cwd(), config.get("storage.torrentsPath"))
      )
    );
    this.app.use(cors());
  }

  setupRoutes() {
    // Podstawowe routy
    this.app.get("/", (req, res) => {
      res.json({
        message: "Blockchain Image Storage API",
        version: "1.0.0",
        endpoints: {
          upload: "/api/upload",
          download: "/api/download/torrent/:filename",
          image: "/api/image/:imageId",
          stats: "/api/stats",
          health: "/api/health",
        },
      });
    });

    // User management endpoints
    this.app.use("/user", userRouter);

    // API routes
    this.app.use("/api", apiRoutes);

    // Obsługa nieznalezionych endpointów
    this.app.use((req, res) => {
      res.status(404).json({ error: "Not Found", path: req.url });
    });

    // Obsługa błędów
    this.app.use((err, req, res, next) => {
      console.error(`Error: ${err.message}`);
      res.status(err.status || 500).json({
        error: err.message || "Internal Server Error",
      });
    });

    const NODE_ID = process.env.NODE_ID || "node1";
    const NODE_PORT = process.env.PORT || 5001;
    const NODE_COUNT = 6;
    const NODES = Array.from(
      { length: NODE_COUNT },
      (_, i) => `http://localhost:${5001 + i}`
    ).filter((url) => !url.endsWith(NODE_PORT));
    const blockchain = new BlockchainNode(NODE_ID, NODES);

    this.app.get("/blockchain/chain", (req, res) => {
      res.json({
        chain: blockchain.chain.map((block) => ({
          index: block.index,
          previousHash: block.previousHash,
          timestamp: block.timestamp,
          transactions: block.transactions.map((tx) => tx.toDict()),
          hash: block.hash,
          nonce: block.nonce,
        })),
        length: blockchain.chain.length,
      });
    });

    this.app.post("/blockchain/verify_transaction", (req, res) => {
      if (blockchain.verifyTransaction(req.body)) {
        res.json({ message: "Transaction verified" });
      } else {
        res.status(400).json({ message: "Transaction verification failed" });
      }
    });

    this.app.post("/blockchain/verify_mined_block", (req, res) => {
      const data = req.body;
      const txs = data.transactions.map(Transaction.fromDict);
      const block = new Block(
        data.index,
        data.previousHash,
        txs,
        data.timestamp
      );
      block.hash = data.hash;
      block.nonce = data.nonce;
      if (blockchain.verifyBlock(block)) {
        blockchain.chain.push(block);
        res.json({ message: "Block verified" });
      } else {
        res.status(400).json({ message: "Block verification failed" });
      }
    });

    this.app.post("/blockchain/transaction/new", (req, res) => {
      const tx = new Transaction(req.body.data, req.body.type || "generic");
      blockchain.broadcastTransaction(tx).then((ok) => {
        if (ok) {
          blockchain.addTransaction(tx);
          res.status(201).json({ message: "Transaction added successfully!" });
        } else {
          res.status(400).json({ message: "Transaction rejected by network" });
        }
      });
    });

    this.app.post(
      "/blockchain/image/process",
      upload.single("image"),
      (req, res) => {
        if (!req.file)
          return res.status(400).json({ error: "No image file provided" });
        blockchain.processImage(req.file.buffer).then((result) => {
          if (result.success) {
            res.json({
              success: true,
              message: "Image successfully stored in blockchain",
              details: result,
            });
          } else {
            res.status(400).json({ success: false, error: result.error });
          }
        });
      }
    );

    this.app.get("/blockchain/mine", (req, res) => {
      blockchain.minePendingTransactions().then((result) => {
        if (result.success) {
          res.json(result);
        } else {
          res.status(400).json(result);
        }
      });
    });
  }

  start() {
    // Uruchom serwer HTTP
    this.server = this.app.listen(this.port, () => {
      console.log(`Server started on port ${this.port}`);
    });

    // Uruchom tracker BitTorrent
    tracker.start();

    // Obsługa zamknięcia serwera
    process.on("SIGTERM", () => this.shutdown());
    process.on("SIGINT", () => this.shutdown());

    return this.server;
  }

  async shutdown() {
    console.log("Shutting down server...");

    // Zatrzymaj tracker
    tracker.stop();

    // Zatrzymaj seedowanie
    await seeder.destroy();

    // Zamknij serwer HTTP
    if (this.server) {
      this.server.close(() => {
        console.log("Server stopped");
        process.exit(0);
      });
    }
  }
}

// Uruchom serwer jeśli plik jest wywoływany bezpośrednio
if (require.main === module) {
  const server = new Server();
  // Start serwera po zakończeniu inicjalizacji
  setTimeout(() => server.start(), 100);
}

module.exports = Server;

