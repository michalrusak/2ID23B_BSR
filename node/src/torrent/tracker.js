const Server = require('bittorrent-tracker').Server
const config = require('config')

class TorrentTracker {
	constructor() {
		this.trackerPort = config.get('tracker.port')
		this.tracker = null
	}

	/**
	 * Uruchamia serwer trackera
	 */
	start() {
		this.tracker = new Server({
			udp: false, // Wyłącz UDP, używaj tylko HTTP
			http: true, // Włącz HTTP
			ws: true, // Włącz WebSockets
			stats: true, // Zbieraj statystyki
			trustProxy: true, // Ufaj nagłówkowi X-Forwarded-For
		})

		// Uruchom tracker HTTP i WebSocket na porcie z konfiguracji
		this.tracker.listen(this.trackerPort, () => {
			console.log(`Torrent tracker server listening on port ${this.trackerPort}`)
		})

		// Obsługa błędów trackera
		this.tracker.on('error', err => {
			console.error(`Tracker error: ${err.message}`)
		})

		// Zdarzenia dla logowania aktywności trackera
		this.tracker.on('start', addr => {
			console.log(`Peer ${addr} connected to tracker`)
		})

		this.tracker.on('complete', addr => {
			console.log(`Peer ${addr} completed download`)
		})

		this.tracker.on('update', addr => {
			console.log(`Peer ${addr} updated`)
		})

		this.tracker.on('stop', addr => {
			console.log(`Peer ${addr} disconnected from tracker`)
		})

		return this.tracker
	}

	/**
	 * Zatrzymuje serwer trackera
	 */
	stop() {
		if (this.tracker) {
			this.tracker.close(() => {
				console.log('Torrent tracker server closed')
			})
		}
	}

	/**
	 * Pobiera statystyki trackera
	 */
	getStats() {
		if (!this.tracker) {
			return { error: 'Tracker not running' }
		}

		const swarms = {}
		for (const infoHash of Object.keys(this.tracker.torrents)) {
			const swarm = this.tracker.torrents[infoHash]
			swarms[infoHash] = {
				complete: swarm.complete,
				incomplete: swarm.incomplete,
				peers: Object.keys(swarm.peers).length,
			}
		}

		return {
			torrents: Object.keys(this.tracker.torrents).length,
			peers: this.tracker._peersCounted || 0,
			swarms,
		}
	}
}

module.exports = new TorrentTracker()
