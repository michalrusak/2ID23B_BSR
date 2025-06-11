const config = require('config')
const axios = require('axios')

class ConsensusManager {
	constructor(nodeId) {
		this.nodeId = nodeId
		this.nodes = config.get('network.nodes')
		this.consensusThreshold = config.get('network.consensusThreshold')
	}

	// Inicjuje proces głosowania dla nowego bloku
	async initiateVoting(block) {
		console.log(`Node ${this.nodeId}: Starting consensus voting for block ${block.hash}`)

		const votingPromises = this.nodes
			.filter(node => node.id !== this.nodeId) // Nie głosujemy na siebie
			.map(node => this.requestVote(node, block))

		// Dodaj swój własny głos
		block.addVote(this.nodeId, true)

		try {
			const votes = await Promise.all(votingPromises)
			const positiveVotes = votes.filter(vote => vote).length + 1 // +1 za własny głos

			console.log(`Node ${this.nodeId}: Consensus result - ${positiveVotes}/${this.nodes.length} votes`)
			return positiveVotes >= this.consensusThreshold
		} catch (error) {
			console.error(`Consensus voting failed: ${error.message}`)
			return false
		}
	}
	// Wysyła żądanie głosowania do innego węzła
	async requestVote(node, block) {
		try {
			const response = await axios.post(
				`http://${node.host}:${node.apiPort}/vote`,
				{
					block: {
						index: block.index,
						timestamp: block.timestamp,
						data: block.data,
						previousHash: block.previousHash,
						hash: block.hash,
						nonce: block.nonce,
					},
					requestingNodeId: this.nodeId,
				},
				{
					timeout: 5000, // 5 sekund timeout
					headers: {
						'Content-Type': 'application/json',
					},
				}
			)

			return response.data.vote
		} catch (error) {
			console.error(`Failed to get vote from node ${node.id}: ${error.message}`)
			return false
		}
	}

	// Weryfikacja bloku przed głosowaniem
	verifyBlock(block, blockchain) {
		console.log(`Node ${this.nodeId}: Verifying block ${block.hash} from node ${block.requestingNodeId || 'unknown'}`)
		const latestBlock = blockchain.getLatestBlock()
		console.log(`Node ${this.nodeId}: Latest block index: ${latestBlock.index}, hash: ${latestBlock.hash}`)
		console.log(`Node ${this.nodeId}: Received block index: ${block.index}, previousHash: ${block.previousHash}`)

		// Sprawdź, czy indeks bloku jest poprawny
		if (block.index !== latestBlock.index + 1) {
			console.log(`Node ${this.nodeId}: Invalid index. Expected ${latestBlock.index + 1}, got ${block.index}`)
			return false
		}

		// Sprawdź, czy poprzedni hash jest poprawny
		if (block.previousHash !== latestBlock.hash) {
			console.log(`Node ${this.nodeId}: Invalid previousHash. Expected ${latestBlock.hash}, got ${block.previousHash}`)
			return false
		}

		// Oblicz i sprawdź hash bloku
		// Musimy stworzyć tymczasowy obiekt Block, aby móc wywołać na nim calculateHash i validateData,
		// ponieważ obiekt 'block' przekazywany w żądaniu to zwykły obiekt JSON, a nie instancja klasy Block.
		const tempBlock = new (require('./block'))(block.index, block.timestamp, block.data, block.previousHash)
		tempBlock.nonce = block.nonce // Ustaw nonce, który został użyty do wykopania bloku
		// Nie ustawiamy tempBlock.hash = block.hash, ponieważ calculateHash() obliczy go na nowo.
		// Hash przekazany w 'block.hash' jest tym, który będziemy weryfikować.

		const calculatedHash = tempBlock.calculateHash() // Oblicz hash na podstawie danych z tempBlock
		console.log(`Node ${this.nodeId}: Received block hash: ${block.hash}, Calculated hash: ${calculatedHash}`)
		if (block.hash !== calculatedHash) {
			console.log(`Node ${this.nodeId}: Invalid hash. Received ${block.hash}, calculated ${calculatedHash}`)
			return false
		}

		// Sprawdź integralność danych
		const isDataValid = tempBlock.validateData() // Użyj metody z instancji Block
		console.log(`Node ${this.nodeId}: Data validation result: ${isDataValid}`)
		if (!isDataValid) {
			console.log(`Node ${this.nodeId}: Invalid data.`)
			return false
		}

		console.log(`Node ${this.nodeId}: Block ${block.hash} verified successfully.`)
		return true
	}

	// Synchronizacja z innymi węzłami w celu uzyskania aktualnego łańcucha
	async synchronizeChain(blockchain) {
		console.log(`Node ${this.nodeId}: Starting chain synchronization`)

		let longestChain = blockchain.chain
		let maxLength = blockchain.chain.length

		const syncPromises = this.nodes
			.filter(node => node.id !== this.nodeId)
			.map(async node => {
				try {
					const response = await axios.get(`http://${node.host}:${node.apiPort}/chain`)
					const nodeChain = response.data.chain

					// Sprawdź, czy otrzymany łańcuch jest dłuższy i poprawny
					if (nodeChain.length > maxLength && this.isValidChain(nodeChain)) {
						maxLength = nodeChain.length
						longestChain = nodeChain
					}
				} catch (error) {
					console.error(`Failed to sync with node ${node.id}: ${error.message}`)
				}
			})

		await Promise.all(syncPromises)

		// Zastąp lokalny łańcuch, jeśli znaleziono dłuższy
		if (longestChain !== blockchain.chain) {
			blockchain.chain = longestChain
			console.log(`Node ${this.nodeId}: Chain replaced with longer one (${maxLength} blocks)`)
			return true
		}

		console.log(`Node ${this.nodeId}: Chain already up to date`)
		return false
	}

	// Sprawdzenie, czy łańcuch jest poprawny
	isValidChain(chain) {
		// Sprawdzenie bloku genesis
		if (JSON.stringify(chain[0]) !== JSON.stringify(this.createGenesisBlock())) {
			return false
		}

		// Sprawdzenie pozostałych bloków
		for (let i = 1; i < chain.length; i++) {
			const currentBlock = chain[i]
			const previousBlock = chain[i - 1]

			// Sprawdzenie hash bloku
			if (currentBlock.hash !== this.calculateBlockHash(currentBlock)) {
				return false
			}

			// Sprawdzenie poprzedniego hash
			if (currentBlock.previousHash !== previousBlock.hash) {
				return false
			}
		}

		return true
	}

	// Pomocnicza funkcja do sprawdzania łańcucha
	createGenesisBlock() {
		return {
			index: 0,
			timestamp: 0,
			data: { message: 'Blockchain Image Storage Genesis Block' },
			previousHash: '0',
			hash: '',
			nonce: 0,
		}
	}

	// Pomocnicza funkcja do sprawdzania łańcucha
	calculateBlockHash(block) {
		const crypto = require('crypto-js')
		return crypto
			.SHA256(block.index + block.timestamp + JSON.stringify(block.data) + block.previousHash + block.nonce)
			.toString()
	}
}

module.exports = ConsensusManager
