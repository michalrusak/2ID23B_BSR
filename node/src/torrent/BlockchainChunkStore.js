const { Buffer } = require('buffer') // Node.js Buffer
const axios = require('axios') // For making HTTP requests to blockchain nodes
const config = require('config') // To get blockchain node configurations

class BlockchainChunkStore {
	constructor(imageId, totalLength, pieceLength, blockchainNodes) {
		this.imageId = imageId
		this.length = totalLength // Całkowita długość zawartości pliku
		this.pieceLength = pieceLength // Długość każdego fragmentu torrenta
		this.blockchainNodes = blockchainNodes // Lista węzłów do odpytania
		this.imageDataCache = null // Prosty cache dla całych danych obrazu
		this.closed = false

		console.log(
			`[BlockchainChunkStore] Initialized for imageId: ${this.imageId}, totalLength: ${this.length}, pieceLength: ${this.pieceLength}`
		)
	}

	// Prywatna metoda do pobrania danych obrazu z blockchaina i zbuforowania ich
	async _fetchAndCacheImageData() {
		if (this.closed) throw new Error('Store is closed')
		if (!this.imageDataCache) {
			console.log(`[BlockchainChunkStore] Fetching image data for ${this.imageId} from blockchain...`)
			let foundImageData = null
			for (const node of this.blockchainNodes) {
				try {
					// Ten endpoint /image-data/:imageId musi zostać zaimplementowany w src/blockchain/node.js
					const response = await axios.get(`http://${node.host}:${node.apiPort}/image-data/${this.imageId}`, {
						timeout: 10000,
					})
					if (response.data && response.data.success && response.data.imageData) {
						foundImageData = response.data.imageData
						console.log(
							`[BlockchainChunkStore] Successfully fetched image data for ${this.imageId} from node ${node.id}`
						)
						break // Znaleziono dane, przerwij pętlę
					}
				} catch (err) {
					console.warn(
						`[BlockchainChunkStore] Failed to get image data for ${this.imageId} from node ${node.id}: ${err.message}`
					)
				}
			}

			if (!foundImageData) {
				console.error(`[BlockchainChunkStore] No image data found for ${this.imageId} on any node!`)
				throw new Error(
					`[BlockchainChunkStore] Failed to fetch image data for ${this.imageId} from any blockchain node.`
				)
			}

			this.imageDataCache = Buffer.from(foundImageData, 'base64')
			console.log(
				`[BlockchainChunkStore] Image data for ${this.imageId} fetched and cached, length: ${this.imageDataCache.length}. Expected totalLength: ${this.length}`
			)

			// Krytyczna weryfikacja: długość pobranych danych musi zgadzać się z metadanymi torrenta
			if (this.imageDataCache.length !== this.length) {
				const errorMessage = `[BlockchainChunkStore] FATAL: Fetched image data length (${this.imageDataCache.length}) does not match torrent metadata length (${this.length}) for ${this.imageId}. Seeding will likely fail or be corrupt.`
				console.error(errorMessage)
				this.imageDataCache = null // Unieważnij cache, jeśli dane są złe
				throw new Error(errorMessage)
			}
			console.log(
				`[BlockchainChunkStore] Image data cache for ${this.imageId} is ready, length: ${this.imageDataCache.length}`
			)
		}
		return this.imageDataCache
	}

	// Metoda wywoływana przez WebTorrent do pobrania fragmentu danych
	get(pieceIndex, options, callback) {
		if (typeof options === 'function') {
			callback = options
			options = null
		}
		if (this.closed) {
			// Użyj process.nextTick, aby uniknąć błędu "Zalgo" - wywołanie zwrotne w tej samej turze pętli zdarzeń
			process.nextTick(() => callback(new Error('Store is closed')))
			return
		}

		console.log(`[BlockchainChunkStore] GET request for pieceIndex: ${pieceIndex} for imageId: ${this.imageId}`)

		this._fetchAndCacheImageData()
			.then(imageData => {
				const offsetInPiece = options && typeof options.offset === 'number' ? options.offset : 0
				const lengthToRead = options && typeof options.length === 'number' ? options.length : this.pieceLength

				const start = pieceIndex * this.pieceLength + offsetInPiece

				if (start >= this.length) {
					console.warn(
						`[BlockchainChunkStore] Attempt to read at or beyond EOF for pieceIndex ${pieceIndex}. Start: ${start}, TotalLength: ${this.length}`
					)
					// Zwróć pusty bufor, jeśli odczyt zaczyna się na końcu pliku lub poza nim
					process.nextTick(() => callback(null, Buffer.alloc(0)))
					return
				}

				const end = Math.min(start + lengthToRead, this.length)
				const chunk = imageData.subarray(start, end)

				console.log(
					`[BlockchainChunkStore] Serving pieceIndex: ${pieceIndex}, offsetInPiece: ${offsetInPiece}, length: ${chunk.length} (requested: ${lengthToRead}), from cache for imageId: ${this.imageId}`
				)
				if (chunk.length === 0) {
					console.warn(
						`[BlockchainChunkStore] WARNING: Returned chunk is empty for pieceIndex: ${pieceIndex}, start: ${start}, end: ${end}`
					)
				}
				if (chunk.length !== lengthToRead && end !== this.length) {
					console.warn(
						`[BlockchainChunkStore] WARNING: Chunk length (${chunk.length}) != requested (${lengthToRead}) for pieceIndex: ${pieceIndex}`
					)
				}
				// Dodatkowe logowanie zawartości pierwszych bajtów chunku (opcjonalnie)
				console.log(`[BlockchainChunkStore] Chunk (first 16 bytes):`, chunk.slice(0, 16))
				process.nextTick(() => {
					console.log(
						`[BlockchainChunkStore] Callback for pieceIndex: ${pieceIndex} called, chunk length: ${chunk.length}`
					)
					callback(null, chunk)
				})
			})
			.catch(err => {
				console.error(
					`[BlockchainChunkStore] Error in GET for pieceIndex ${pieceIndex} for imageId: ${this.imageId}:`,
					err
				)
				process.nextTick(() => callback(err))
			})
	}

	// Metoda wymagana przez WebTorrent, dla seedera tylko do odczytu może być no-op
	put(pieceIndex, buffer, callback) {
		if (this.closed) {
			process.nextTick(() => callback(new Error('Store is closed')))
			return
		}
		// Ten magazyn jest tylko do odczytu z blockchaina dla celów seedowania
		console.warn(
			`[BlockchainChunkStore] PUT called for pieceIndex: ${pieceIndex}, but this is a read-only store. Operation ignored.`
		)
		process.nextTick(() => callback(null))
	}

	// Metoda do zamknięcia magazynu
	close(callback) {
		console.log(`[BlockchainChunkStore] CLOSE called for imageId: ${this.imageId}`)
		this.closed = true
		this.imageDataCache = null // Wyczyść cache
		if (callback) process.nextTick(callback)
	}

	// Metoda do zniszczenia magazynu (może być aliasem do close)
	destroy(callback) {
		console.log(`[BlockchainChunkStore] DESTROY called for imageId: ${this.imageId}`)
		this.close(callback)
	}
}

module.exports = BlockchainChunkStore
