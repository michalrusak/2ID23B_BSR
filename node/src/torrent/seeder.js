const WebTorrent = require("webtorrent");
const fs = require("fs");
const path = require("path");
const config = require("config");
const PythonBlockchainChunkStore = require("./PythonBlockchainChunkStore"); // Nowy import

class TorrentSeeder {
  constructor() {
    this.client = new WebTorrent();
    this.torrentsPath = path.resolve(
      process.cwd(),
      config.get("storage.torrentsPath")
    );
    this.activeTorrents = new Map(); // DODANO: Inicjalizacja activeTorrents
    // this.imagesPath = path.resolve(process.cwd(), config.get('storage.imagesPath')) // Już niepotrzebne, jeśli nie przechowujemy lokalnie

    console.log("[TorrentSeeder] Initialized");
    console.log(
      `[TorrentSeeder] Torrents path for .torrent files: ${this.torrentsPath}`
    );
    // console.log(`[TorrentSeeder] Images path: ${this.imagesPath}`)

    this.client.on("error", (err) => {
      console.error("[TorrentSeeder] WebTorrent client error:", err);
    });

    this.client.on("torrent", (torrent) => {
      console.log(
        `[TorrentSeeder] Torrent added: ${torrent.infoHash} - ${torrent.name}`
      );
      console.log(
        `[TorrentSeeder] Torrent files: ${torrent.files
          .map((f) => f.name)
          .join(", ")}`
      );
      console.log(`[TorrentSeeder] Torrent trackers: ${torrent.announce}`);
      torrent.on("ready", () => {
        console.log(
          `[TorrentSeeder] Torrent ready to seed: ${torrent.infoHash} - ${torrent.name}`
        );
        console.log(`[TorrentSeeder] Seeders: ${torrent.numPeers}`); // numPeers includes seeders and leechers
      });
      torrent.on("warning", (err) => {
        console.warn(
          `[TorrentSeeder] Torrent warning for ${torrent.infoHash}:`,
          err
        );
      });
      torrent.on("error", (err) => {
        console.error(
          `[TorrentSeeder] Torrent error for ${torrent.infoHash}:`,
          err
        );
      });
      torrent.on("download", (bytes) => {
        // console.log(`[TorrentSeeder] Torrent ${torrent.infoHash} downloaded: ${bytes} bytes`);
      });
      torrent.on("upload", (bytes) => {
        console.log(
          `[TorrentSeeder] Torrent ${torrent.infoHash} uploaded: ${bytes} bytes`
        ); // ODKOMENTOWANO
      });
      torrent.on("wire", function (wire, addr) {
        console.log(
          `[TorrentSeeder] Connected to peer ${wire.peerId} at ${addr} for torrent ${torrent.infoHash}`
        );
      });
    });
  }

  async seedFileFromBlockchain(torrentFilePath, imageId) {
    const { default: parseTorrent } = await import("parse-torrent"); // Dynamiczny import

    console.log(
      `[TorrentSeeder] Attempting to seed file FROM BLOCKCHAIN. Torrent path: ${torrentFilePath}, ImageID: ${imageId}`
    );
    try {
      if (!fs.existsSync(torrentFilePath)) {
        console.error(
          `[TorrentSeeder] Torrent file not found at: ${torrentFilePath}`
        );
        throw new Error(`Torrent file not found at: ${torrentFilePath}`);
      }

      const torrentFileBuffer = fs.readFileSync(torrentFilePath);
      console.log(
        `[TorrentSeeder] Read torrent file. Path: ${torrentFilePath}, Buffer length: ${torrentFileBuffer.length}`
      ); // Dodano logowanie rozmiaru bufora
      const parsedTorrent = await parseTorrent(torrentFileBuffer); // Dodano await

      console.log(`[TorrentSeeder] Parsed torrent object:`, parsedTorrent); // Dodano logowanie całego obiektu parsedTorrent

      // Sprawdzenie, czy parsedTorrent jest zdefiniowany przed próbą dostępu do właściwości
      if (
        !parsedTorrent ||
        !parsedTorrent.length ||
        !parsedTorrent.pieceLength
      ) {
        const errMsg = `[TorrentSeeder] Critical error: Torrent metadata is missing, invalid, or incomplete. Name: ${
          parsedTorrent ? parsedTorrent.name : "N/A"
        }, Length: ${
          parsedTorrent ? parsedTorrent.length : "N/A"
        }, PieceLength: ${parsedTorrent ? parsedTorrent.pieceLength : "N/A"}`;
        console.error(errMsg);
        throw new Error(errMsg);
      }

      // Utworz klasę magazynu specyficzną dla tego torrent
      class TorrentSpecificStore extends PythonBlockchainChunkStore {
        constructor(chunkLength, storeOpts) {
          console.log(
            `[TorrentSeeder] TorrentSpecificStore constructor called. chunkLength: ${chunkLength}`
          );
          console.log(`[TorrentSeeder] storeOpts:`, storeOpts);
          // Przekaż parametry do nadklasy
          super(imageId, parsedTorrent.length, chunkLength);
        }
      }

      const options = {
        name: parsedTorrent.name, // Nazwa torrenta
        announce: parsedTorrent.announce, // Lista trackerów
        store: TorrentSpecificStore, // Przekaż klasę bezpośrednio
        // Nie podajemy `path`, ponieważ `store` obsługuje dostarczanie danych
      };

      console.log(
        `[TorrentSeeder] Adding torrent to client with TorrentSpecificStore for imageId: ${imageId}`
      );

      this.client.add(torrentFileBuffer, options, (torrent) => {
        console.log(
          `[TorrentSeeder] Client is seeding (from blockchain) ${torrent.files.length} files for torrent: ${torrent.name} (infoHash: ${torrent.infoHash})`
        );
        console.log(`[TorrentSeeder] Files being seeded (metadata):`);
        torrent.files.forEach((file) => {
          console.log(
            `  - ${file.name} (path in torrent: ${file.path}, length: ${file.length})`
          );
        });
        console.log(
          `[TorrentSeeder] Torrent announce URLs: ${torrent.announce.join(
            ", "
          )}`
        );
        console.log(`[TorrentSeeder] Torrent magnet URI: ${torrent.magnetURI}`);
      });
    } catch (error) {
      console.error(
        `[TorrentSeeder] Error seeding file from blockchain: ${error.message}`,
        error
      );
      throw error; // Rzuć błąd dalej, aby obsłużyć go w routes.js
    }
  }

  /**
   * Rozpoczyna seedowanie pliku torrent na podstawie infoHash
   * @param {string} torrentId - InfoHash lub magnetURI
   * @param {string} filePath - Ścieżka do pliku, który ma być seedowany
   */
  async seedTorrentByInfoHash(torrentId, filePath) {
    return new Promise(async (resolve, reject) => {
      try {
        // Sprawdź czy plik istnieje
        await fs.access(filePath);

        // Jeśli torrent jest już seedowany, zwróć go
        for (const [infoHash, torrent] of this.activeTorrents.entries()) {
          if (infoHash === torrentId || torrent.magnetURI === torrentId) {
            return resolve({
              message: "Torrent already being seeded",
              torrent: {
                name: torrent.name,
                infoHash,
                magnetURI: torrent.magnetURI,
              },
            });
          }
        }

        this.client.add(
          torrentId,
          { path: path.dirname(filePath) },
          (torrent) => {
            console.log(`Started seeding by infoHash ${torrent.name}`);

            resolve({
              message: "Successfully started seeding",
              torrent: {
                name: torrent.name,
                infoHash: torrent.infoHash,
                magnetURI: torrent.magnetURI,
              },
            });
          }
        );
      } catch (error) {
        console.error(`Error seeding by infoHash: ${error.message}`);
        reject(error);
      }
    });
  }

  /**
   * Zatrzymuje seedowanie torrentu
   * @param {string} infoHash - InfoHash torrentu do zatrzymania
   */
  stopSeeding(infoHash) {
    const torrent = this.activeTorrents.get(infoHash);

    if (torrent) {
      torrent.destroy(() => {
        console.log(`Stopped seeding ${torrent.name}`);
        this.activeTorrents.delete(infoHash);
      });
      return true;
    }

    return false;
  }

  /**
   * Pobiera listę wszystkich seedowanych torrentów
   * @returns {Array} - Lista aktywnych torrentów
   */
  getActiveTorrents() {
    const torrents = [];

    for (const torrent of this.client.torrents) {
      torrents.push({
        name: torrent.name,
        infoHash: torrent.infoHash,
        magnetURI: torrent.magnetURI,
        downloaded: torrent.downloaded,
        uploaded: torrent.uploaded,
        downloadSpeed: torrent.downloadSpeed,
        uploadSpeed: torrent.uploadSpeed,
        progress: torrent.progress,
        ratio: torrent.ratio,
        numPeers: torrent.numPeers,
        timeRemaining: torrent.timeRemaining,
      });
    }

    return torrents;
  }

  /**
   * Zatrzymuje klienta WebTorrent i wszystkie aktywne torrenty
   */
  async destroy() {
    return new Promise((resolve, reject) => {
      this.client.destroy((err) => {
        if (err) {
          console.error(`Error destroying WebTorrent client: ${err.message}`);
          reject(err);
        } else {
          console.log("WebTorrent client destroyed");
          if (this.activeTorrents) {
            // DODANO: Sprawdzenie czy activeTorrents istnieje
            this.activeTorrents.clear();
          }
          resolve();
        }
      });
    });
  }
}

module.exports = TorrentSeeder;

