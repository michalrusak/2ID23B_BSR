const { Buffer } = require("buffer");
const axios = require("axios");
require("dotenv").config();

class PythonBlockchainChunkStore {
  constructor(imageId, totalLength, pieceLength) {
    this.imageId = imageId;
    this.length = totalLength; // Całkowita długość zawartości pliku
    this.pieceLength = pieceLength; // Długość każdego fragmentu torrenta
    this.pythonBackendUrl =
      process.env.PYTHON_BACKEND_URL || "http://localhost:5001";
    this.imageDataCache = null; // Cache dla danych obrazu
    this.closed = false;

    console.log(
      `[PythonBlockchainChunkStore] Initialized for imageId: ${this.imageId}, totalLength: ${this.length}, pieceLength: ${this.pieceLength}`
    );
    console.log(
      `[PythonBlockchainChunkStore] Python backend URL: ${this.pythonBackendUrl}`
    );
  }
  // Pobierz dane obrazu z Python blockchain
  async _fetchAndCacheImageData() {
    if (this.closed) throw new Error("Store is closed");
    if (!this.imageDataCache) {
      console.log(
        `[PythonBlockchainChunkStore] Fetching image data for ${this.imageId} from Python blockchain...`
      );

      try {
        // Spróbuj najpierw endpoint specyficzny dla obrazu
        try {
          const imageResponse = await axios.get(
            `${this.pythonBackendUrl}/blockchain/image/data/${this.imageId}`,
            {
              timeout: 10000,
            }
          );

          if (
            imageResponse.data &&
            imageResponse.data.success &&
            imageResponse.data.imageData
          ) {
            this.imageDataCache = Buffer.from(
              imageResponse.data.imageData,
              "base64"
            );
            console.log(
              `[PythonBlockchainChunkStore] Successfully cached image data from specific endpoint. Size: ${this.imageDataCache.length} bytes`
            );
            return this.imageDataCache;
          }
        } catch (specificError) {
          console.log(
            `[PythonBlockchainChunkStore] Specific image endpoint failed, trying chain search...`
          );
        }

        // Fallback: pobierz cały blockchain
        const chainResponse = await axios.get(
          `${this.pythonBackendUrl}/blockchain/chain`,
          {
            timeout: 10000,
          }
        );

        if (!chainResponse.data || !chainResponse.data.chain) {
          throw new Error("No blockchain data received from Python backend");
        }

        // Znajdź obraz w blockchain - szukaj po imageId lub po kolejności
        let foundImageData = null;
        for (const block of chainResponse.data.chain) {
          for (const transaction of block.transactions) {
            if (transaction.type === "image" && transaction.data) {
              // Sprawdź czy to nasz obraz
              if (
                transaction.imageId === this.imageId ||
                block.index.toString() === this.imageId
              ) {
                console.log(
                  `[PythonBlockchainChunkStore] Found image in block ${block.index} for imageId ${this.imageId}`
                );
                foundImageData = transaction.data;
                break;
              }
            }
          }
          if (foundImageData) break;
        }

        // Jeśli nie znaleziono po ID, weź pierwszy dostępny obraz
        if (!foundImageData) {
          console.log(
            `[PythonBlockchainChunkStore] No image found by ID, taking first available image...`
          );
          for (const block of chainResponse.data.chain) {
            for (const transaction of block.transactions) {
              if (transaction.type === "image" && transaction.data) {
                console.log(
                  `[PythonBlockchainChunkStore] Using image from block ${block.index} as fallback`
                );
                foundImageData = transaction.data;
                break;
              }
            }
            if (foundImageData) break;
          }
        }

        if (!foundImageData) {
          throw new Error(`No image data found for ${this.imageId}`);
        }

        // Konwertuj z base64 do Buffer
        this.imageDataCache = Buffer.from(foundImageData, "base64");
        console.log(
          `[PythonBlockchainChunkStore] Successfully cached image data. Size: ${this.imageDataCache.length} bytes`
        );
      } catch (error) {
        console.error(
          `[PythonBlockchainChunkStore] Error fetching image data: ${error.message}`
        );
        throw error;
      }
    }
    return this.imageDataCache;
  }

  // Metoda wywoływana przez WebTorrent do pobrania fragmentu danych
  get(pieceIndex, options, callback) {
    if (typeof options === "function") {
      callback = options;
      options = {};
    }
    if (this.closed) {
      return callback(new Error("Store is closed"));
    }

    console.log(
      `[PythonBlockchainChunkStore] GET request for pieceIndex: ${pieceIndex} for imageId: ${this.imageId}`
    );

    this._fetchAndCacheImageData()
      .then((imageData) => {
        if (!imageData) {
          console.error(
            `[PythonBlockchainChunkStore] No image data available for ${this.imageId}`
          );
          return callback(
            new Error(`No image data available for ${this.imageId}`)
          );
        }

        const startOffset = pieceIndex * this.pieceLength;
        const endOffset = Math.min(
          startOffset + this.pieceLength,
          imageData.length
        );

        if (startOffset >= imageData.length) {
          console.log(
            `[PythonBlockchainChunkStore] Piece ${pieceIndex} is beyond data length`
          );
          return callback(new Error("Piece index out of bounds"));
        }

        const pieceData = imageData.slice(startOffset, endOffset);
        console.log(
          `[PythonBlockchainChunkStore] Returning piece ${pieceIndex}: ${
            pieceData.length
          } bytes (${startOffset}-${endOffset - 1})`
        );
        callback(null, pieceData);
      })
      .catch((err) => {
        console.error(
          `[PythonBlockchainChunkStore] Error in GET for piece ${pieceIndex}:`,
          err
        );
        callback(err);
      });
  }

  // Metoda wymagana przez WebTorrent (read-only store)
  put(pieceIndex, buffer, callback) {
    if (this.closed) {
      return callback(new Error("Store is closed"));
    }
    // Read-only store - nie zapisujemy
    console.warn(
      `[PythonBlockchainChunkStore] PUT called for pieceIndex: ${pieceIndex}, but this is a read-only store. Operation ignored.`
    );
    process.nextTick(() => callback(null));
  }

  // Zamknij store
  close(callback) {
    console.log(
      `[PythonBlockchainChunkStore] CLOSE called for imageId: ${this.imageId}`
    );
    this.closed = true;
    this.imageDataCache = null;
    if (callback) process.nextTick(callback);
  }

  // Zniszcz store
  destroy(callback) {
    console.log(
      `[PythonBlockchainChunkStore] DESTROY called for imageId: ${this.imageId}`
    );
    this.close(callback);
  }
}

module.exports = PythonBlockchainChunkStore;
