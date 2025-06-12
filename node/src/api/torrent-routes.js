const express = require("express");
const multer = require("multer");
const path = require("path");
const fs = require("fs").promises;
const config = require("config");
const torrentCreator = require("../torrent/torrent-creator");
const TorrentSeeder = require("../torrent/seeder");
const axios = require("axios");

const torrentSeeder = new TorrentSeeder();

// Load environment variables
require("dotenv").config();

// Konfiguracja przechowywania plików
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, config.get("storage.temporaryPath"));
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + "-" + Math.round(Math.random() * 1e9);
    cb(
      null,
      file.fieldname + "-" + uniqueSuffix + path.extname(file.originalname)
    );
  },
});

const upload = multer({
  storage,
  limits: { fileSize: config.get("api.maxFileSize") },
  fileFilter: (req, file, cb) => {
    // Akceptuj tylko pliki graficzne
    if (file.mimetype.startsWith("image/")) {
      cb(null, true);
    } else {
      cb(new Error("Dozwolone są tylko pliki graficzne"), false);
    }
  },
});

// Inicjalizacja routera
const router = express.Router();

// Endpoint do tworzenia torrenta z obrazu z blockchain
router.post("/create-torrent/:imageId", async (req, res) => {
  console.log(
    `[${new Date().toISOString()}] Create torrent request for imageId: ${
      req.params.imageId
    }`
  );

  try {
    const { imageId } = req.params;
    const pythonBackendUrl =
      process.env.PYTHON_BACKEND_URL || "http://localhost:5001";
    // Pobierz dane obrazu z Python blockchain
    console.log("Fetching image data from Python blockchain...");
    const blockchainResponse = await axios.get(
      `${pythonBackendUrl}/blockchain/image/data/${imageId}`
    );

    if (!blockchainResponse.data || !blockchainResponse.data.success) {
      throw new Error("Image not found in blockchain");
    }

    const imageData = blockchainResponse.data.imageData;
    if (!imageData) {
      return res
        .status(404)
        .json({ error: "Image data not found in blockchain" });
    }

    console.log(`Found image data, length: ${imageData.length}`);

    // Zapisz dane obrazu do pliku tymczasowego
    const tempDir = config.get("storage.temporaryPath");
    const tempImagePath = path.join(tempDir, `${imageId}.jpg`); // Domyślnie jpg

    // Konwertuj z base64 i zapisz
    const imageBuffer = Buffer.from(imageData, "base64");
    await fs.writeFile(tempImagePath, imageBuffer);
    console.log(`Image saved to temporary file: ${tempImagePath}`);

    // Utwórz plik torrent
    console.log("Creating torrent file...");
    const torrentInfo = await torrentCreator.generateTorrentForImage(
      tempImagePath,
      imageId
    );
    console.log(`Torrent created: ${torrentInfo.downloadUrl}`);

    // Rozpocznij seedowanie z blockchain
    console.log("Starting seeding from blockchain...");
    await torrentSeeder.seedFileFromBlockchain(
      torrentInfo.torrentPath,
      imageId
    );
    console.log(`Seeding started for image ${imageId}`);

    // Usuń plik tymczasowy
    try {
      await fs.unlink(tempImagePath);
      console.log("Temporary image file removed");
    } catch (unlinkError) {
      console.warn(`Could not remove temporary file: ${unlinkError.message}`);
    }

    res.json({
      success: true,
      message: "Torrent created and seeding started",
      imageId: imageId,
      torrentDownloadUrl: torrentInfo.downloadUrl,
      torrentPath: torrentInfo.torrentPath,
    });
  } catch (error) {
    console.error(`Error creating torrent: ${error.message}`);
    res.status(500).json({
      error: "Failed to create torrent",
      details: error.message,
    });
  }
});

// Endpoint do pobierania pliku torrent
router.get("/download/torrent/:filename", async (req, res) => {
  console.log(
    `[${new Date().toISOString()}] Torrent download request for: ${
      req.params.filename
    }`
  );

  const configuredTorrentsPath = config.get("storage.torrentsPath");
  const absoluteTorrentsPath = path.resolve(
    process.cwd(),
    configuredTorrentsPath
  );
  const torrentPath = path.join(absoluteTorrentsPath, req.params.filename);

  console.log(`Attempting to access torrent file at: ${torrentPath}`);

  try {
    // Sprawdź czy plik istnieje
    await fs.access(torrentPath);
    console.log(`Torrent file found at: ${torrentPath}`);

    // Ustaw odpowiednie nagłówki
    res.setHeader("Content-Type", "application/x-bittorrent");
    res.setHeader(
      "Content-Disposition",
      `attachment; filename="${req.params.filename}"`
    );

    // Wyślij plik
    res.sendFile(torrentPath, (err) => {
      if (err) {
        console.error(`Error sending torrent file: ${err.message}`);
        if (!res.headersSent) {
          res
            .status(500)
            .json({ error: "Błąd podczas wysyłania pliku torrent" });
        }
      } else {
        console.log(`Torrent file ${req.params.filename} sent successfully.`);
      }
    });
  } catch (error) {
    console.error(`Błąd podczas pobierania pliku torrent: ${error.message}`);
    if (error.code === "ENOENT") {
      res.status(404).json({
        error: "Nie znaleziono pliku torrent",
        details: `Plik nie istnieje w lokalizacji: ${torrentPath}`,
      });
    } else {
      res
        .status(500)
        .json({ error: "Błąd serwera podczas próby dostępu do pliku torrent" });
    }
  }
});

// Endpoint do sprawdzenia statusu seedowania
router.get("/seeding/status", (req, res) => {
  try {
    const activeTorrents = torrentSeeder.getActiveTorrents();
    res.json({
      success: true,
      activeTorrents: activeTorrents.length,
      torrents: activeTorrents,
    });
  } catch (error) {
    console.error(`Error getting seeding status: ${error.message}`);
    res.status(500).json({
      error: "Failed to get seeding status",
      details: error.message,
    });
  }
});

// Endpoint do sprawdzenia zdrowia API torrent
router.get("/health", (req, res) => {
  res.json({
    status: "healthy",
    service: "torrent-api",
    timestamp: new Date().toISOString(),
    activeTorrents: torrentSeeder.getActiveTorrents().length,
  });
});

module.exports = router;
