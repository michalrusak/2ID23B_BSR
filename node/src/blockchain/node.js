const express = require('express')
const bodyParser = require('body-parser')
const WebSocket = require('ws')
const Blockchain = require('./chain')
const ConsensusManager = require('./consensus')
const config = require('config')
const path = require('path')

class BlockchainNode {
	constructor(nodeId) {
		this.nodeId = nodeId
		this.config = this.getNodeConfig(nodeId)
		if (!this.config) {
			throw new Error(`Configuration for node ${nodeId} not found!`)
		}

		this.blockchain = new Blockchain()
		this.consensusManager = new ConsensusManager(nodeId)
		this.peers = new Map() // Połączenia P2P z innymi węzłami

		this.initHttpServer()
		this.initP2PServer()
		this.connectToPeers()
	}

	getNodeConfig(nodeId) {
		const nodes = config.get('network.nodes')
		return nodes.find(node => node.id === nodeId)
	}

	initHttpServer() {
		const app = express()
		console.log(`Node ${this.nodeId}: Initializing HTTP server...`) // Dodatkowe logowanie
		app.use(bodyParser.json({ limit: '50mb' }))
		app.use(bodyParser.urlencoded({ extended: true, limit: '50mb' }))

		// Endpoint do pobrania całego łańcucha
		app.get('/chain', (req, res) => {
			console.log(`Node ${this.nodeId}: Received request for /chain`) // Dodatkowe logowanie
			res.json({
				chain: this.blockchain.chain,
				length: this.blockchain.chain.length,
			})
		})

		// Endpoint do głosowania na blok
		app.post('/vote', (req, res) => {
			const { block, requestingNodeId } = req.body

			// Weryfikacja bloku
			const isValid = this.consensusManager.verifyBlock(block, this.blockchain)
			console.log(
				`Node ${this.nodeId}: Voting ${isValid ? 'YES' : 'NO'} for block ${block.hash} from node ${requestingNodeId}`
			)

			// Wysłanie głosu
			res.json({ vote: isValid })
		})

		// Endpoint do dodania nowego bloku przez inny węzeł
		app.post('/block', (req, res) => {
			const { block } = req.body

			// Weryfikacja i dodanie bloku do łańcucha
			if (this.blockchain.isValidNewBlock(block)) {
				this.blockchain.chain.push(block)
				res.json({ success: true, message: 'Block added to chain' })
			} else {
				res.status(400).json({ success: false, message: 'Invalid block' })
			}
		})

		// Endpoint do rejestracji nowego obrazu
		app.post('/store-image', async (req, res) => {
			try {
				const { imageData, imageId, crc } = req.body
				console.log(
					`Node ${this.nodeId}: Received image ${imageId}, imageData length: ${
						imageData ? imageData.length : 'undefined'
					}`
				) // Dodatkowe logowanie

				// Tworzenie bloku z danymi obrazu
				const blockData = {
					type: 'image',
					imageId,
					imageData,
					crc,
					timestamp: Date.now(),
				}

				// Dodanie bloku do oczekujących i rozpoczęcie procesu konsensusu
				const block = this.blockchain.addPendingBlock(blockData)
				console.log(`Node ${this.nodeId}: Starting consensus for block ${block.hash} (imageId: ${imageId})...`) // Dodatkowe logowanie
				const consensusReached = await this.consensusManager.initiateVoting(block)
				console.log(
					`Node ${this.nodeId}: Consensus reached: ${consensusReached} for block ${block.hash} (imageId: ${imageId})`
				) // Dodatkowe logowanie

				if (consensusReached) {
					// Roześlij informację o nowym bloku do innych węzłów
					this.broadcastBlock(block)

					res.json({
						success: true,
						message: 'Image stored successfully',
						blockHash: block.hash,
					})
				} else {
					res.status(400).json({
						success: false,
						message: 'Consensus not reached for this block',
					})
				}
			} catch (error) {
				console.error(`Error storing image: ${error.message}`)
				res.status(500).json({ success: false, message: error.message })
			}
		})

		// Endpoint do pobrania danych obrazu na podstawie imageId
		app.get('/image-data/:imageId', (req, res) => {
			const { imageId } = req.params
			console.log(`[Node ${this.nodeId}] Received request for image data: ${imageId}`)
			try {
				const blockContainingImage = this.blockchain.chain.find(block => block.data && block.data.imageId === imageId)

				if (blockContainingImage) {
					console.log(`[Node ${this.nodeId}] Found image ${imageId} in block ${blockContainingImage.index}`)
					let imageDataToSend = blockContainingImage.data.imageData
					// Sprawdź typ imageData i w razie potrzeby przekonwertuj na base64
					console.log(
						`[Node ${this.nodeId}] Type of imageData before sending for ${imageId}: ${typeof imageDataToSend}`
					)
					if (Buffer.isBuffer(imageDataToSend)) {
						console.log(`[Node ${this.nodeId}] imageData for ${imageId} is a Buffer. Converting to base64 string.`)
						imageDataToSend = imageDataToSend.toString('base64')
					} else if (
						typeof imageDataToSend === 'object' &&
						imageDataToSend.type === 'Buffer' &&
						Array.isArray(imageDataToSend.data)
					) {
						// Obsługa przypadku, gdy Buffer został zserializowany do obiektu { type: 'Buffer', data: [...] }
						console.log(
							`[Node ${this.nodeId}] imageData for ${imageId} is a serialized Buffer object. Converting to base64 string.`
						)
						imageDataToSend = Buffer.from(imageDataToSend.data).toString('base64')
					}
					res.json({ success: true, imageData: imageDataToSend })
				} else {
					console.warn(`[Node ${this.nodeId}] Image data not found for imageId: ${imageId}`)
					res.status(404).json({ success: false, message: 'Image data not found' })
				}
			} catch (error) {
				console.error(`[Node ${this.nodeId}] Error retrieving image data for ${imageId}:`, error)
				res.status(500).json({ success: false, message: 'Internal server error while retrieving image data' })
			}
		})

		// Uruchomienie serwera HTTP
		const PORT = this.config.apiPort
		console.log(`Node ${this.nodeId}: Attempting to start HTTP server on port ${PORT}...`) // Dodatkowe logowanie
		app.listen(PORT, () => {
			console.log(`Node ${this.nodeId}: HTTP server running on port ${PORT}`)
		})
	}

	initP2PServer() {
		const server = new WebSocket.Server({ port: this.config.p2pPort })

		server.on('connection', socket => {
			this.initConnection(socket)
		})

		console.log(`Node ${this.nodeId}: P2P server running on port ${this.config.p2pPort}`)
	}

	connectToPeers() {
		// Połącz z innymi węzłami
		this.consensusManager.nodes.forEach(node => {
			// Nie łącz z samym sobą
			if (node.id !== this.nodeId) {
				const url = `ws://${node.host}:${node.p2pPort}`
				try {
					const socket = new WebSocket(url)
					socket.on('open', () => {
						this.initConnection(socket)

						// Wysłanie informacji o sobie
						this.send(socket, {
							type: 'HANDSHAKE',
							nodeId: this.nodeId,
						})
					})

					socket.on('error', error => {
						console.error(`Connection error to ${url}: ${error.message}`)
					})
				} catch (error) {
					console.error(`Failed to connect to peer ${url}: ${error.message}`)
				}
			}
		})
	}

	initConnection(socket) {
		socket.on('message', data => {
			const message = JSON.parse(data)
			this.handleMessage(socket, message)
		})

		socket.on('close', () => {
			// Usuń zamknięte połączenie z listy peerów
			for (const [nodeId, peerSocket] of this.peers.entries()) {
				if (peerSocket === socket) {
					this.peers.delete(nodeId)
					console.log(`Node ${this.nodeId}: Connection closed with node ${nodeId}`)
					break
				}
			}
		})

		socket.on('error', error => {
			console.error(`Socket error: ${error.message}`)
			socket.close()
		})
	}

	handleMessage(socket, message) {
		switch (message.type) {
			case 'HANDSHAKE':
				// Zapisanie połączenia z innym węzłem
				this.peers.set(message.nodeId, socket)
				console.log(`Node ${this.nodeId}: Connected to node ${message.nodeId}`)
				break

			case 'NEW_BLOCK':
				// Otrzymano informację o nowym bloku
				const block = message.block
				const latestBlock = this.blockchain.getLatestBlock() // Pobierz aktualny ostatni blok
				if (this.blockchain.isValidNewBlock(block, latestBlock)) {
					// Przekaż latestBlock
					this.blockchain.chain.push(block)
					console.log(`Node ${this.nodeId}: Added new block from network ${block.hash}`)
				} else {
					console.log(`Node ${this.nodeId}: Received invalid new block ${block.hash} from network.`)
				}
				break

			case 'REQUEST_CHAIN':
				// Wysłanie łańcucha do węzła, który o to poprosił
				this.send(socket, {
					type: 'CHAIN_RESPONSE',
					chain: this.blockchain.chain,
				})
				break

			case 'CHAIN_RESPONSE':
				// Otrzymano łańcuch od innego węzła
				const receivedChain = message.chain
				if (receivedChain.length > this.blockchain.chain.length && this.consensusManager.isValidChain(receivedChain)) {
					console.log(`Node ${this.nodeId}: Replacing chain with received one`)
					this.blockchain.chain = receivedChain
				}
				break
		}
	}

	send(socket, message) {
		socket.send(JSON.stringify(message))
	}

	// Roześlij blok do wszystkich połączonych węzłów
	broadcastBlock(block) {
		for (const socket of this.peers.values()) {
			this.send(socket, {
				type: 'NEW_BLOCK',
				block,
			})
		}
	}

	// Wyczyść stare nieużywane połączenia
	cleanupConnections() {
		for (const [nodeId, socket] of this.peers.entries()) {
			if (socket.readyState === WebSocket.CLOSED) {
				this.peers.delete(nodeId)
				console.log(`Node ${this.nodeId}: Removed closed connection with node ${nodeId}`)
			}
		}
	}
}

// Uruchomienie węzła
if (require.main === module) {
	const nodeId = process.env.NODE_ID || process.argv[2]

	if (!nodeId) {
		console.error('Please provide a node ID as an environment variable or command line argument')
		process.exit(1)
	}

	try {
		const node = new BlockchainNode(nodeId)

		// Okresowe czyszczenie połączeń
		setInterval(() => {
			node.cleanupConnections()
		}, 30000)

		// Okresowa synchronizacja łańcucha
		setInterval(async () => {
			await node.consensusManager.synchronizeChain(node.blockchain)
		}, 60000)
	} catch (error) {
		console.error(`Failed to start node: ${error.message}`)
		process.exit(1)
	}
}

module.exports = BlockchainNode
