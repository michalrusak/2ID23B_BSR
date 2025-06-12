const Block = require('./block')
const config = require('config')

class Blockchain {
	constructor() {
		this.chain = [this.createGenesisBlock()]
		this.pendingBlocks = [] // Zmieniono z pendingTransactions na pendingBlocks
		this.difficulty = 1 // Zmieniono z 4 na 1
		this.nodes = new Set() // Zbiór węzłów w sieci
	}

	createGenesisBlock() {
		return new Block(0, 0, { message: 'Blockchain Image Storage Genesis Block' }, '0') // Użyto stałego znacznika czasu 0
	}

	getLatestBlock() {
		return this.chain[this.chain.length - 1]
	}

	// Dodanie nowego bloku do oczekujących na konsensus
	addPendingBlock(data) {
		const block = new Block(this.chain.length, Date.now(), data, this.getLatestBlock().hash)
		console.log(`[Blockchain] Starting to mine block ${block.timestamp} for imageId: ${data.imageId}...`) // Dodatkowe logowanie
		block.mineBlock(this.difficulty)
		console.log(`[Blockchain] Finished mining block ${block.hash} for imageId: ${data.imageId}.`) // Dodatkowe logowanie
		this.pendingBlocks.push(block)
		return block
	}

	// Dodanie głosu na blok
	voteOnBlock(blockHash, nodeId, isValid) {
		const blockIndex = this.pendingBlocks.findIndex(b => b.hash === blockHash)
		if (blockIndex === -1) return false

		const block = this.pendingBlocks[blockIndex]
		const voteAdded = block.addVote(nodeId, isValid)

		// Sprawdzenie, czy osiągnięto konsensus
		if (block.hasReachedConsensus(this.consensusThreshold)) {
			this.chain.push(block)
			this.pendingBlocks.splice(blockIndex, 1)
			return { added: true, consensus: true }
		}

		return { added: voteAdded, consensus: false }
	}

	// Sprawdzenie, czy blok jest ważny do dodania do łańcucha
	isValidNewBlock(block, latestBlock) {
		// console.log('Validating new block:', block);
		// console.log('Against latest block:', latestBlock);

		// Przed walidacją hasha i danych, utwórz nową instancję Block
		// aby upewnić się, że mamy dostęp do metod prototypu.
		// Zakładamy, że 'block' to obiekt z danymi, który przyszedł przez sieć.
		const tempBlock = new Block(block.index, block.timestamp, block.data, block.previousHash)
		// Skopiuj nonce i hash z oryginalnego obiektu bloku,
		// ponieważ są one wynikiem miningu/konsensusu i nie są ustawiane w konstruktorze w ten sam sposób,
		// lub mogły zostać nadpisane przez calculateHash() w konstruktorze Block, jeśli dane są identyczne.
		tempBlock.nonce = block.nonce
		tempBlock.hash = block.hash // Ważne: używamy oryginalnego hasha do porównania z obliczonym i do walidacji.

		if (tempBlock.index !== latestBlock.index + 1) {
			console.log(`Invalid index: expected ${latestBlock.index + 1}, got ${tempBlock.index}`)
			return false
		}

		if (tempBlock.previousHash !== latestBlock.hash) {
			console.log(`Invalid previous hash: expected ${latestBlock.hash}, got ${tempBlock.previousHash}`)
			return false
		}

		// Użyj tempBlock do walidacji, ponieważ ma on metody prototypu
		const calculatedHash = tempBlock.calculateHash() // Oblicz hash na podstawie danych tempBlock (w tym nonce)
		if (tempBlock.hash !== calculatedHash) {
			console.log('Invalid hash: received', tempBlock.hash, 'calculated', calculatedHash)
			console.log('Block data used for calculation:', {
				index: tempBlock.index,
				timestamp: tempBlock.timestamp,
				data: tempBlock.data,
				previousHash: tempBlock.previousHash,
				nonce: tempBlock.nonce,
			})
			return false
		}

		if (!tempBlock.validateData()) {
			// Użyj tempBlock
			console.log('Invalid data in new block')
			return false
		}

		return true
	}

	// Sprawdzenie całego łańcucha
	isChainValid() {
		for (let i = 1; i < this.chain.length; i++) {
			const currentBlock = this.chain[i]
			const previousBlock = this.chain[i - 1]

			if (!currentBlock.isValid(previousBlock.hash)) {
				return false
			}
		}
		return true
	}

	// Znalezienie bloku zawierającego konkretne dane (np. po identyfikatorze obrazu)
	findBlockByImageId(imageId) {
		return this.chain.find(block => block.data.imageId === imageId)
	}
}

module.exports = Blockchain
