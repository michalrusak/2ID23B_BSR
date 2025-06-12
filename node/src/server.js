const express = require('express')
const bodyParser = require('body-parser')
const path = require('path')
const config = require('config')
const fs = require('fs').promises
const apiRoutes = require('./api/routes')
const tracker = require('./torrent/tracker')
const seeder = require('./torrent/seeder')

class Server {
	constructor() {
		this.app = express()
		this.port = config.get('api.port')
		this.setupDirectories()
		this.setupMiddlewares()
		this.setupRoutes()
	}

	async setupDirectories() {
		// Upewnij się, że wszystkie katalogi istnieją
		const directories = [
			config.get('storage.imagesPath'),
			config.get('storage.torrentsPath'),
			config.get('storage.temporaryPath'),
		]

		for (const dir of directories) {
			try {
				await fs.mkdir(dir, { recursive: true })
				console.log(`Directory created or already exists: ${dir}`)
			} catch (error) {
				console.error(`Error creating directory ${dir}: ${error.message}`)
			}
		}
	}

	setupMiddlewares() {
		// Konfiguracja parsera JSON z większym limitem dla obrazów
		this.app.use(bodyParser.json({ limit: '50mb' }))
		this.app.use(bodyParser.urlencoded({ extended: true, limit: '50mb' }))

		// Middleware do logowania żądań
		this.app.use((req, res, next) => {
			console.log(`${new Date().toISOString()} - ${req.method} ${req.url}`)
			next()
		})

		// Middleware do obsługi błędów CORS
		this.app.use((req, res, next) => {
			res.header('Access-Control-Allow-Origin', '*')
			res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE')
			res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

			if (req.method === 'OPTIONS') {
				return res.sendStatus(200)
			}
			next()
		})

		// Middleware do statycznych plików
		this.app.use('/files', express.static(path.join(process.cwd(), config.get('storage.imagesPath'))))
		this.app.use('/torrents', express.static(path.join(process.cwd(), config.get('storage.torrentsPath'))))
	}

	setupRoutes() {
		// Podstawowe routy
		this.app.get('/', (req, res) => {
			res.json({
				message: 'Blockchain Image Storage API',
				version: '1.0.0',
				endpoints: {
					upload: '/api/upload',
					download: '/api/download/torrent/:filename',
					image: '/api/image/:imageId',
					stats: '/api/stats',
					health: '/api/health',
				},
			})
		})

		// API routes
		this.app.use('/api', apiRoutes)

		// Obsługa nieznalezionych endpointów
		this.app.use((req, res) => {
			res.status(404).json({ error: 'Not Found', path: req.url })
		})

		// Obsługa błędów
		this.app.use((err, req, res, next) => {
			console.error(`Error: ${err.message}`)
			res.status(err.status || 500).json({
				error: err.message || 'Internal Server Error',
			})
		})
	}

	start() {
		// Uruchom serwer HTTP
		this.server = this.app.listen(this.port, () => {
			console.log(`Server started on port ${this.port}`)
		})

		// Uruchom tracker BitTorrent
		tracker.start()

		// Obsługa zamknięcia serwera
		process.on('SIGTERM', () => this.shutdown())
		process.on('SIGINT', () => this.shutdown())

		return this.server
	}

	async shutdown() {
		console.log('Shutting down server...')

		// Zatrzymaj tracker
		tracker.stop()

		// Zatrzymaj seedowanie
		await seeder.destroy()

		// Zamknij serwer HTTP
		if (this.server) {
			this.server.close(() => {
				console.log('Server stopped')
				process.exit(0)
			})
		}
	}
}

// Uruchom serwer jeśli plik jest wywoływany bezpośrednio
if (require.main === module) {
	const server = new Server()
	server.start()
}

module.exports = Server
