const express = require("express");
const bodyParser = require("body-parser");
const path = require("path");
const config = require("config");
const fs = require("fs").promises;
const cors = require("cors");
const torrentRoutes = require("./api/torrent-routes");
const tracker = require("./torrent/tracker");
require("dotenv").config();

class TorrentServer {
  constructor() {
    this.app = express();
    this.port = process.env.TORRENT_PORT || 3000;
    this.setupDirectories();
    this.setupMiddlewares();
    this.setupRoutes();
  }

  async setupDirectories() {
    // Upewnij się, że wszystkie katalogi istnieją
    const directories = [
      config.get("storage.torrentsPath"),
      config.get("storage.temporaryPath"),
    ];

    for (const dir of directories) {
      try {
        await fs.mkdir(path.resolve(process.cwd(), dir), { recursive: true });
        console.log(`Directory created or exists: ${dir}`);
      } catch (error) {
        console.error(`Error creating directory ${dir}: ${error.message}`);
        throw error;
      }
    }
  }

  setupMiddlewares() {
    // Enable CORS for frontend
    this.app.use(
      cors({
        origin: ["http://localhost:4200", "http://localhost:3000"],
        credentials: true,
      })
    );

    // Konfiguracja parsera JSON
    this.app.use(bodyParser.json({ limit: "50mb" }));
    this.app.use(bodyParser.urlencoded({ extended: true, limit: "50mb" }));

    // Middleware do logowania żądań
    this.app.use((req, res, next) => {
      console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
      next();
    });

    // Middleware do statycznych plików torrent
    this.app.use(
      "/torrents",
      express.static(
        path.join(process.cwd(), config.get("storage.torrentsPath"))
      )
    );
  }

  setupRoutes() {
    // Podstawowe info o API
    this.app.get("/", (req, res) => {
      res.json({
        message: "Blockchain Torrent API",
        version: "1.0.0",
        service: "torrent-server",
        endpoints: {
          createTorrent: "POST /api/create-torrent/:imageId",
          downloadTorrent: "GET /api/download/torrent/:filename",
          seedingStatus: "GET /api/seeding/status",
          health: "GET /api/health",
        },
        tracker: {
          port: config.get("tracker.port"),
          announce: config.get("tracker.announce"),
        },
      });
    });

    // API routes
    this.app.use("/api", torrentRoutes);

    // Obsługa nieznalezionych endpointów
    this.app.use((req, res) => {
      res.status(404).json({
        error: "Not Found",
        path: req.url,
        availableEndpoints: [
          "POST /api/create-torrent/:imageId",
          "GET /api/download/torrent/:filename",
          "GET /api/seeding/status",
          "GET /api/health",
        ],
      });
    });

    // Obsługa błędów
    this.app.use((err, req, res, next) => {
      console.error(`Error: ${err.message}`);
      res.status(err.status || 500).json({
        error: err.message || "Internal Server Error",
        stack: process.env.NODE_ENV === "development" ? err.stack : undefined,
      });
    });
  }

  start() {
    // Uruchom serwer HTTP
    this.server = this.app.listen(this.port, () => {
      console.log(`Torrent API server running on port ${this.port}`);
      console.log(`API available at: http://localhost:${this.port}`);
      console.log(
        `Torrent files served from: ${config.get("storage.torrentsPath")}`
      );
    });

    // Uruchom tracker BitTorrent
    console.log("Starting BitTorrent tracker...");
    tracker.start();

    // Obsługa zamknięcia serwera
    process.on("SIGTERM", () => this.shutdown());
    process.on("SIGINT", () => this.shutdown());

    return this.server;
  }

  async shutdown() {
    console.log("Shutting down torrent server...");

    // Zatrzymaj tracker
    tracker.stop();

    // Zamknij serwer HTTP
    if (this.server) {
      this.server.close(() => {
        console.log("Torrent server closed");
        process.exit(0);
      });
    }
  }
}

// Uruchom serwer jeśli plik jest wywoływany bezpośrednio
if (require.main === module) {
  const server = new TorrentServer();
  server.start();
}

module.exports = TorrentServer;
