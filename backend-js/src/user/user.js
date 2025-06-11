const express = require("express");
const jwt = require("jsonwebtoken");
const bcrypt = require("bcryptjs");
const { Pool } = require("pg");
const multer = require("multer");
const fs = require("fs");
const path = require("path");
require("dotenv").config();

const router = express.Router();
const upload = multer();

const pool = new Pool({
  host: process.env.POSTGRES_HOST || "localhost",
  port: process.env.POSTGRES_PORT || 5433, // zmiana z 5432 na 5433
  user: process.env.POSTGRES_USER || "blockchain_user",
  password: process.env.POSTGRES_PASSWORD || "blockchain_password",
  database: process.env.POSTGRES_DB || "blockchain_db",
});

const SECRET_KEY = process.env.SECRET_KEY || "secret";

async function initDb() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      id SERIAL PRIMARY KEY,
      username VARCHAR(50) UNIQUE NOT NULL,
      password_hash VARCHAR(200) NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
  `);
  await pool.query(`
    CREATE TABLE IF NOT EXISTS images (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id),
      image_data BYTEA NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
  `);
}
initDb();

function tokenRequired(req, res, next) {
  const authHeader = req.headers["authorization"];
  if (!authHeader) return res.status(401).json({ message: "Token is missing" });
  const token = authHeader.split(" ")[1];
  if (!token) return res.status(401).json({ message: "Token is missing" });
  jwt.verify(token, SECRET_KEY, (err, decoded) => {
    if (err) return res.status(401).json({ message: "Invalid token" });
    req.userId = decoded.user_id;
    next();
  });
}

router.post("/register", async (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password)
    return res.status(400).json({ message: "Missing required fields" });
  const hash = await bcrypt.hash(password, 10);
  try {
    const result = await pool.query(
      "INSERT INTO users (username, password_hash) VALUES ($1, $2) RETURNING id",
      [username, hash]
    );
    res.status(201).json({
      message: "User created successfully",
      user_id: result.rows[0].id,
    });
  } catch (err) {
    if (err.code === "23505")
      return res.status(400).json({ message: "Username already exists" });
    res.status(500).json({ message: "Database error" });
  }
});

router.post("/login", async (req, res) => {
  const { username, password } = req.body || {};
  if (!username || !password)
    return res.status(400).json({ message: "Missing required fields" });
  const result = await pool.query(
    "SELECT id, password_hash FROM users WHERE username = $1",
    [username]
  );
  const user = result.rows[0];
  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).json({ message: "Invalid credentials" });
  }
  const token = jwt.sign(
    { user_id: user.id, exp: Math.floor(Date.now() / 1000) + 24 * 3600 },
    SECRET_KEY
  );
  res.json({ token });
});

router.post(
  "/upload-image",
  tokenRequired,
  upload.single("image"),
  async (req, res) => {
    if (!req.file)
      return res.status(400).json({ message: "No image provided" });
    const imageData = req.file.buffer;
    const result = await pool.query(
      "INSERT INTO images (user_id, image_data) VALUES ($1, $2) RETURNING id",
      [req.userId, imageData]
    );
    res.status(201).json({
      message: "Image uploaded successfully",
      image_id: result.rows[0].id,
    });
  }
);

router.get("/get-image/:image_id", tokenRequired, async (req, res) => {
  const imageId = req.params.image_id;
  const result = await pool.query(
    "SELECT image_data FROM images WHERE id = $1",
    [imageId]
  );
  const image = result.rows[0];
  if (!image) return res.status(404).json({ message: "Image not found" });
  res.set("Content-Type", "image/jpeg");
  res.send(image.image_data);
});

module.exports = router;
