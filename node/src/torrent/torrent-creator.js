const createTorrent = require("create-torrent");
const fs = require("fs").promises;
const path = require("path");
const config = require("config");

class TorrentCreator {
  constructor() {
    this.torrentsPath = config.get("storage.torrentsPath");
    this.trackerAnnounce = config.get("tracker.announce");

    // Upewnijmy się, że katalog na torrenty istnieje
    this.ensureDirectoryExists();
  }

  async ensureDirectoryExists() {
    try {
      await fs.mkdir(this.torrentsPath, { recursive: true });
      console.log("Torrents directory created or already exists");
    } catch (error) {
      console.error(`Error creating torrents directory: ${error.message}`);
      throw error;
    }
  }

  /**
   * Tworzy plik .torrent dla podanego pliku obrazu
   * @param {string} filePath - Ścieżka do pliku obrazu
   * @param {string} name - Nazwa dla pliku torrent
   * @returns {Promise<string>} - Ścieżka do utworzonego pliku torrent
   */
  async createTorrentFile(filePath, name) {
    return new Promise((resolve, reject) => {
      // Zachowaj rozszerzenie pliku w nazwie torrenta
      const originalExtension = path.extname(filePath);
      const torrentFileName = originalExtension
        ? `${name}${originalExtension}`
        : `${name}.jpg`;

      createTorrent(
        filePath,
        {
          name: torrentFileName, // Użyj nazwy z rozszerzeniem
          comment: "Created by Blockchain Image Storage",
          createdBy: "Blockchain Image Storage",
          private: false,
          announceList: [this.trackerAnnounce],
          urlList: [],
        },
        (err, torrentBuffer) => {
          if (err) {
            return reject(err);
          }

          const torrentPath = path.join(this.torrentsPath, `${name}.torrent`);

          fs.writeFile(torrentPath, torrentBuffer)
            .then(() => resolve(torrentPath))
            .catch(reject);
        }
      );
    });
  }

  /**
   * Generuje plik torrent dla obrazu przechowywanego w blockchain
   * @param {string} imageFilePath - Ścieżka do pliku obrazu
   * @param {string} imageId - Identyfikator obrazu
   * @returns {Promise<Object>} - Informacje o utworzonym torrencie
   */
  async generateTorrentForImage(imageFilePath, imageId) {
    try {
      // Sprawdź czy plik istnieje
      await fs.access(imageFilePath);

      // Utwórz plik torrent
      const torrentPath = await this.createTorrentFile(imageFilePath, imageId);

      // Usuń plik tymczasowy po utworzeniu torrenta
      try {
        await fs.unlink(imageFilePath);
        console.log(
          `[TorrentCreator] Successfully deleted temporary file: ${imageFilePath}`
        );
      } catch (unlinkError) {
        console.error(
          `[TorrentCreator] Error deleting temporary file ${imageFilePath}: ${unlinkError.message}`
        );
        // Można zdecydować, czy błąd usuwania pliku powinien zatrzymać proces, czy tylko zostać zalogowany
      }

      return {
        torrentPath,
        imageId,
        originalFilePath: imageFilePath,
        downloadUrl: `/download/torrent/${imageId}.torrent`,
      };
    } catch (error) {
      console.error(`Error generating torrent: ${error.message}`);
      throw error;
    }
  }

  /**
   * Pobiera informacje o pliku torrent
   * @param {string} torrentPath - Ścieżka do pliku torrent
   * @returns {Promise<Object>} - Informacje o torrencie
   */
  async getTorrentInfo(torrentPath) {
    const parseTorrent = require("parse-torrent");

    try {
      const torrentBuffer = await fs.readFile(torrentPath);
      const info = parseTorrent(torrentBuffer);

      return {
        name: info.name,
        infoHash: info.infoHash,
        size: info.length,
        files: info.files,
        announce: info.announce,
        pieceLength: info.pieceLength,
      };
    } catch (error) {
      console.error(`Error parsing torrent: ${error.message}`);
      throw error;
    }
  }
}

module.exports = new TorrentCreator();

