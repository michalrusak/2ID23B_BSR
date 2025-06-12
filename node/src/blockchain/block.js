const crypto = require('crypto-js')
const { calculateCRC } = require('../storage/crc-validator')

class Block {
	constructor(index, timestamp, data, previousHash = '') {
		this.index = index
		this.timestamp = timestamp
		this.data = data
		this.previousHash = previousHash
		this.hash = this.calculateHash()
		this.nonce = 0
		this.votes = [] // Lista głosów od węzłów
	}

	calculateHash() {
		return crypto
			.SHA256(this.index + this.timestamp + JSON.stringify(this.data) + this.previousHash + this.nonce)
			.toString()
	}

	// Prosta implementacja Proof of Work
	mineBlock(difficulty) {
		while (this.hash.substring(0, difficulty) !== Array(difficulty + 1).join('0')) {
			this.nonce++
			this.hash = this.calculateHash()
		}
		console.log(`Block mined: ${this.hash}`)
	}

	// Dodanie głosu od węzła
	addVote(nodeId, isValid) {
		// Sprawdzenie, czy węzeł już głosował
		if (!this.votes.some(vote => vote.nodeId === nodeId)) {
			this.votes.push({ nodeId, isValid })
			return true
		}
		return false
	}

	// Sprawdzenie, czy blok osiągnął konsensus
	hasReachedConsensus(threshold) {
		const validVotes = this.votes.filter(vote => vote.isValid).length
		return validVotes >= threshold
	}

	// Weryfikacja integralności danych bloku
	validateData() {
		// Jeśli dane zawierają obraz, sprawdź sumę kontrolną
		if (this.data.imageData) {
			const storedCRC = this.data.crc
			const calculatedCRC = calculateCRC(this.data.imageData)
			return storedCRC === calculatedCRC
		}
		return true
	}

	// Weryfikacja całego bloku
	isValid(previousHash) {
		// Sprawdzenie hash poprzedniego bloku
		if (this.previousHash !== previousHash) {
			return false
		}

		// Sprawdzenie własnego hash
		if (this.hash !== this.calculateHash()) {
			return false
		}

		// Sprawdzenie integralności danych
		if (!this.validateData()) {
			return false
		}

		return true
	}
}

module.exports = Block
