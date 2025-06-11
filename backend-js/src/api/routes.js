const express = require('express')
const multer = require('multer')
const path = require('path')
const fs = require('fs').promises
const config = require('config')
const imageProcessor = require('../storage/image-processor')
const torrentCreator = require('../torrent/torrent-creator')
const TorrentSeeder = require('../torrent/seeder') // Zmieniono nazwę, aby wskazywała, że to klasa
const axios = require('axios') // Dodano import axios
const torrentSeeder = new TorrentSeeder()

// Pobierz dostępne węzły z konfiguracji
const nodes = config.get('network.nodes')

// Konfiguracja przechowywania plików
const storage = multer.diskStorage({
	destination: (req, file, cb) => {
		cb(null, config.get('storage.temporaryPath'))
	},
	filename: (req, file, cb) => {
		const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1e9)
		cb(null, file.fieldname + '-' + uniqueSuffix + path.extname(file.originalname))
	},
})

const upload = multer({
	storage,
	limits: { fileSize: config.get('api.maxFileSize') },
	fileFilter: (req, file, cb) => {
		// Akceptuj tylko pliki graficzne
		if (file.mimetype.startsWith('image/')) {
			cb(null, true)
		} else {
			cb(new Error('Dozwolone są tylko pliki graficzne'), false)
		}
	},
})

// Inicjalizacja routera
const router = express.Router()

// Endpoint do przesyłania obrazu
router.post('/upload', upload.single('image'), async (req, res) => {
	console.log(`[${new Date().toISOString()}] Upload request started`)

	try {
		if (!req.file) {
			console.log('No file uploaded')
			return res.status(400).json({ error: 'Nie przesłano pliku' })
		}

		console.log(`Processing image: ${req.file.originalname}, size: ${req.file.size} bytes`)

		// Przetwórz obraz i zapisz w formacie base64
		const imageInfo = await imageProcessor.processImage(req.file.path, req.file.originalname)
		console.log(`Image processed: ${imageInfo.imageId}`)
		console.log(`imageData length: ${imageInfo.imageData.length}`)

		// Zmień nazwę pliku tymczasowego na imageId, aby zgadzała się z nazwą w torrencie
		const tempDir = config.get('storage.temporaryPath')
		const originalTempFilePath = req.file.path // np. data/temp/image-timestamp-random.png
		// Zakładamy, że imageInfo.imageId już zawiera poprawne rozszerzenie pliku
		const newTempFilePath = path.join(tempDir, imageInfo.imageId)

		console.log(`Renaming temporary file from ${originalTempFilePath} to ${newTempFilePath}`)
		await fs.rename(originalTempFilePath, newTempFilePath)
		console.log(`Temporary file renamed successfully.`)

		// Użyj nowej ścieżki (newTempFilePath) do tworzenia torrenta i seedowania
		const filePathForTorrentAndSeeding = newTempFilePath

		// Wybierz losowy węzeł blockchain do wysłania obrazu
		const randomNode = nodes[Math.floor(Math.random() * nodes.length)]
		console.log(`Selected blockchain node: ${randomNode.id} at ${randomNode.host}:${randomNode.apiPort}`)

		// Wyślij obraz do węzła blockchain
		console.log('Sending image to blockchain...')
		const blockchainResponse = await axios.post(
			`http://${randomNode.host}:${randomNode.apiPort}/store-image`,
			{
				imageData: imageInfo.imageData,
				imageId: imageInfo.imageId,
				crc: imageInfo.crc,
			},
			{
				timeout: 60000, // Zwiększony timeout do 60 sekund
				headers: {
					'Content-Type': 'application/json',
				},
			}
		)

		console.log(`Blockchain response: ${JSON.stringify(blockchainResponse.data)}`)

		if (!blockchainResponse.data.success) {
			throw new Error('Nie udało się zapisać obrazu w blockchain')
		}

		// Utwórz plik torrent dla obrazu
		console.log('Creating torrent file...')
		const torrentInfo = await Promise.race([
			torrentCreator.generateTorrentForImage(filePathForTorrentAndSeeding, imageInfo.imageId),
			new Promise((_, reject) => setTimeout(() => reject(new Error('Torrent creation timeout')), 15000)),
		])
		console.log(`Torrent created: ${torrentInfo.downloadUrl}`)

		// Rozpocznij seedowanie pliku
		console.log('Starting seeding...')
		// Upewnij się, że torrentInfo.torrentPath jest absolutna lub poprawnie rozwiązywana przez seedFile
		// Obecnie torrentCreator zwraca ścieżkę względną, ale seedFile zdaje się ją obsługiwać
		// Dla pewności można by zrobić: const absoluteTorrentPath = path.resolve(process.cwd(), torrentInfo.torrentPath);
		await torrentSeeder.seedFileFromBlockchain(torrentInfo.torrentPath, imageInfo.imageId)
		console.log(`[API] Seeding torrent ${torrentInfo.torrentPath} for image ${imageInfo.imageId} from blockchain.`)

		// Zwróć sukces i informacje o zapisanym obrazie
		const response = {
			success: true,
			message: 'Obraz został pomyślnie przesłany i zapisany w blockchain',
			imageId: imageInfo.imageId,
			blockHash: blockchainResponse.data.blockHash,
			torrentDownloadUrl: torrentInfo.downloadUrl,
		}
		console.log(`Upload completed successfully for ${imageInfo.imageId}`)
		res.json(response)
	} catch (error) {
		console.error(`[${new Date().toISOString()}] Upload error: ${error.message}`)
		console.error(error.stack)
		res.status(500).json({ error: error.message })
	}
})

// Endpoint do pobierania pliku torrent
router.get('/download/torrent/:filename', async (req, res) => {
	console.log(`[${new Date().toISOString()}] Torrent download request for: ${req.params.filename}`)
	console.log(`Current working directory (cwd): ${process.cwd()}`)
	const configuredTorrentsPath = config.get('storage.torrentsPath')
	console.log(`Configured torrents path: ${configuredTorrentsPath}`)
	const absoluteTorrentsPath = path.resolve(process.cwd(), configuredTorrentsPath)
	console.log(`Absolute torrents path resolved to: ${absoluteTorrentsPath}`)
	const torrentPath = path.join(absoluteTorrentsPath, req.params.filename)
	console.log(`Attempting to access torrent file at: ${torrentPath}`)

	try {
		// Sprawdź czy plik istnieje
		await fs.access(torrentPath, fs.constants.F_OK) // Sprawdź tylko istnienie pliku
		console.log(`Torrent file found at: ${torrentPath}`)

		// Pobierz informacje o torrencie (opcjonalne, jeśli tylko wysyłamy plik)
		// const torrentInfo = await torrentCreator.getTorrentInfo(torrentPath);

		// Ustaw odpowiednie nagłówki
		res.setHeader('Content-Type', 'application/x-bittorrent')
		res.setHeader('Content-Disposition', `attachment; filename="${req.params.filename}"`)

		// Wyślij plik
		res.sendFile(torrentPath, err => {
			if (err) {
				console.error(`Error sending torrent file: ${err.message}`)
				if (!res.headersSent) {
					res.status(500).json({ error: 'Błąd podczas wysyłania pliku torrent' })
				}
			} else {
				console.log(`Torrent file ${req.params.filename} sent successfully.`)
			}
		})
	} catch (error) {
		console.error(`Błąd podczas pobierania pliku torrent: ${error.message}`)
		if (error.code === 'ENOENT') {
			console.log(`Torrent file not found at: ${torrentPath}`)
			res
				.status(404)
				.json({ error: 'Nie znaleziono pliku torrent', details: `Plik nie istnieje w lokalizacji: ${torrentPath}` })
		} else {
			res.status(500).json({ error: 'Błąd serwera podczas próby dostępu do pliku torrent' })
		}
	}
})

// Endpoint do pobierania obrazu z blockchain
router.get('/image/:imageId', async (req, res) => {
	try {
		// Przechodzimy przez wszystkie węzły, aby znaleźć obraz
		let imageFound = false

		for (const node of nodes) {
			try {
				// Pobierz łańcuch blockchain z węzła
				const response = await axios.get(`http://${node.host}:${node.apiPort}/chain`, {
					timeout: 10000, // 10 sekund timeout
				})
				const chain = response.data.chain

				// Szukaj bloku z obrazem o podanym ID
				const imageBlock = chain.find(
					block => block.data && block.data.type === 'image' && block.data.imageId === req.params.imageId
				)

				if (imageBlock) {
					// Sprawdź poprawność CRC
					const isValid = verifyCRC(imageBlock.data.imageData, imageBlock.data.crc)

					if (!isValid) {
						return res.status(400).json({ error: 'Wykryto uszkodzenie obrazu' })
					}

					// Przekonwertuj base64 na bufor
					const imageBuffer = Buffer.from(imageBlock.data.imageData, 'base64')

					// Określ typ MIME na podstawie rozszerzenia pliku
					const mimeType = imageProcessor.getMimeType(req.params.imageId)

					// Ustaw odpowiednie nagłówki
					res.setHeader('Content-Type', mimeType)
					res.setHeader('Content-Disposition', `inline; filename="${req.params.imageId}"`)

					// Wyślij obraz
					res.send(imageBuffer)
					imageFound = true
					break
				}
			} catch (nodeError) {
				console.error(`Błąd podczas komunikacji z węzłem ${node.id}: ${nodeError.message}`)
				// Kontynuuj z następnym węzłem
			}
		}

		if (!imageFound) {
			res.status(404).json({ error: 'Nie znaleziono obrazu o podanym ID' })
		}
	} catch (error) {
		console.error(`Błąd podczas pobierania obrazu: ${error.message}`)
		res.status(500).json({ error: error.message })
	}
})

// Endpoint do wyświetlania statystyk sieci
router.get('/stats', async (req, res) => {
	console.log(`[${new Date().toISOString()}] Stats request started`)

	try {
		// Zbierz statystyki z węzłów
		const nodesStats = await Promise.all(
			nodes.map(async node => {
				try {
					console.log(`Checking node ${node.id} at ${node.host}:${node.apiPort}`)
					const response = await axios.get(`http://${node.host}:${node.apiPort}/chain`, {
						timeout: 5000, // 5 sekund timeout dla stats
					})
					console.log(`Node ${node.id} responded with chain length: ${response.data.length}`)
					return {
						nodeId: node.id,
						chainLength: response.data.length,
						status: 'online',
					}
				} catch (error) {
					console.error(`Node ${node.id} is offline: ${error.message}`)
					return {
						nodeId: node.id,
						status: 'offline',
						error: error.message,
					}
				}
			})
		)

		// Pobierz statystyki seedowanych torrentów
		const activeTorrents = torrentSeeder.getActiveTorrents()
		console.log(`Active torrents: ${activeTorrents.length}`)

		const response = {
			nodes: nodesStats,
			torrents: {
				active: activeTorrents.length,
				details: activeTorrents,
			},
		}
		console.log(`Stats response: ${JSON.stringify(response)}`)
		res.json(response)
	} catch (error) {
		console.error(`[${new Date().toISOString()}] Stats error: ${error.message}`)
		console.error(error.stack)
		res.status(500).json({ error: error.message })
	}
})

// Endpoint do sprawdzenia zdrowia systemu
router.get('/health', (req, res) => {
	res.json({
		status: 'ok',
		timestamp: Date.now(),
	})
})

module.exports = router
