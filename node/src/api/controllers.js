const imageProcessor = require('../storage/image-processor')
const torrentCreator = require('../torrent/torrent-creator')
const torrentSeeder = require('../torrent/seeder')
const axios = require('axios')
const config = require('config')

// Pobierz dostępne węzły z konfiguracji
const nodes = config.get('network.nodes')

/**
 * Kontroler do obsługi przesyłania obrazów
 */
exports.uploadImage = async (req, file, originalFilename) => {
	try {
		// Przetwórz obraz
		const imageInfo = await imageProcessor.processImage(file.path, originalFilename)

		// Wybierz węzły do wysłania obrazu (przynajmniej 4 z 6)
		const selectedNodes = [...nodes].sort(() => 0.5 - Math.random()).slice(0, config.get('network.consensusThreshold'))

		// Wyślij obraz do wybranych węzłów blockchain
		const uploadPromises = selectedNodes.map(node =>
			axios.post(`http://${node.host}:${node.apiPort}/store-image`, {
				imageData: imageInfo.imageData,
				imageId: imageInfo.imageId,
				crc: imageInfo.crc,
			})
		)

		const results = await Promise.allSettled(uploadPromises)
		const successfulUploads = results.filter(
			result => result.status === 'fulfilled' && result.value.data.success
		).length

		if (successfulUploads < config.get('network.consensusThreshold')) {
			throw new Error(
				`Nie osiągnięto konsensusu. Sukces: ${successfulUploads}/${config.get('network.consensusThreshold')}`
			)
		}

		// Utwórz plik torrent dla obrazu
		const torrentInfo = await torrentCreator.generateTorrentForImage(file.path, imageInfo.imageId)

		// Rozpocznij seedowanie pliku
		await torrentSeeder.seedFile(torrentInfo.torrentPath, file.path)

		return {
			success: true,
			imageId: imageInfo.imageId,
			blockHash: results[0].value.data.blockHash, // Hash bloku z pierwszego węzła
			torrentDownloadUrl: torrentInfo.downloadUrl,
		}
	} catch (error) {
		console.error(`Error uploading image: ${error.message}`)
		throw error
	}
}

/**
 * Kontroler do pobierania obrazu
 */
exports.getImage = async imageId => {
	try {
		// Przeszukaj wszystkie węzły w poszukiwaniu obrazu
		let imageBlock = null

		for (const node of nodes) {
			try {
				const response = await axios.get(`http://${node.host}:${node.apiPort}/chain`)
				const chain = response.data.chain

				// Szukaj bloku z żądanym imageId
				const block = chain.find(b => b.data && b.data.type === 'image' && b.data.imageId === imageId)

				if (block) {
					// Weryfikuj sumę kontrolną CRC
					const isValidCRC = imageProcessor.verifyBlockchainImage(block.data.imageData, block.data.crc)

					if (isValidCRC) {
						imageBlock = block
						break
					} else {
						console.warn(`Found image ${imageId} at node ${node.id} but CRC check failed`)
					}
				}
			} catch (error) {
				console.error(`Error querying node ${node.id}: ${error.message}`)
			}
		}

		if (imageBlock) {
			// Pobierz dane obrazu
			return {
				success: true,
				imageData: imageBlock.data.imageData,
				mimeType: imageProcessor.getMimeType(imageId),
				imageId,
			}
		} else {
			throw new Error('Image not found in blockchain')
		}
	} catch (error) {
		console.error(`Error retrieving image: ${error.message}`)
		throw error
	}
}

/**
 * Kontroler do pobierania statystyk systemu
 */
exports.getSystemStats = async () => {
	try {
		// Pobierz statystyki z węzłów blockchain
		const nodePromises = nodes.map(async node => {
			try {
				const response = await axios.get(`http://${node.host}:${node.apiPort}/chain`, { timeout: 2000 })
				return {
					nodeId: node.id,
					status: 'online',
					blocksCount: response.data.length,
					lastUpdated: new Date().toISOString(),
				}
			} catch (error) {
				return {
					nodeId: node.id,
					status: 'offline',
					error: error.message,
				}
			}
		})

		const nodesStatus = await Promise.all(nodePromises)

		// Pobierz informacje o aktywnych torrentach
		const torrents = torrentSeeder.getActiveTorrents()

		return {
			system: {
				timestamp: Date.now(),
				uptime: process.uptime(),
			},
			blockchain: {
				nodes: nodesStatus,
				onlineNodesCount: nodesStatus.filter(n => n.status === 'online').length,
				consensusThreshold: config.get('network.consensusThreshold'),
			},
			torrents: {
				active: torrents.length,
				details: torrents,
			},
		}
	} catch (error) {
		console.error(`Error getting system stats: ${error.message}`)
		throw error
	}
}
