const fs = require('fs').promises
const path = require('path')
const config = require('config')
const { calculateCRC } = require('./crc-validator')

class ImageProcessor {
	constructor() {
		this.imagesPath = config.get('storage.imagesPath')
		this.tempPath = config.get('storage.temporaryPath')

		// Upewniamy się, że katalogi istnieją
		this.ensureDirectoriesExist()
	}

	async ensureDirectoriesExist() {
		try {
			await fs.mkdir(this.imagesPath, { recursive: true })
			await fs.mkdir(this.tempPath, { recursive: true })
			console.log('Storage directories created or already exist')
		} catch (error) {
			console.error(`Error creating directories: ${error.message}`)
			throw error
		}
	}

	// Konwertuje obraz do base64
	async imageToBase64(imagePath) {
		try {
			const data = await fs.readFile(imagePath)
			return data.toString('base64')
		} catch (error) {
			console.error(`Error converting image to base64: ${error.message}`)
			throw error
		}
	}

	// Zapisuje obraz z base64
	async saveBase64Image(base64Data, filename) {
		try {
			const buffer = Buffer.from(base64Data, 'base64')
			const filePath = path.join(this.imagesPath, filename)
			await fs.writeFile(filePath, buffer)
			return filePath
		} catch (error) {
			console.error(`Error saving base64 image: ${error.message}`)
			throw error
		}
	}

	// Generuje unikalną nazwę pliku
	generateUniqueFilename(originalFilename) {
		const timestamp = Date.now()
		const randomString = Math.random().toString(36).substring(2, 8)
		const extension = path.extname(originalFilename)
		const basename = path.basename(originalFilename, extension)

		return `${basename}-${timestamp}-${randomString}${extension}`
	}

	// Procesuje obraz przed dodaniem do blockchain
	async processImage(filePath, originalFilename) {
		try {
			// Konwertuj obraz na base64
			const base64Data = await this.imageToBase64(filePath)

			// Oblicz sumę kontrolną CRC
			const crc = calculateCRC(base64Data)

			// Generuj unikalny identyfikator dla obrazu
			const uniqueFilename = this.generateUniqueFilename(originalFilename)

			return {
				imageId: uniqueFilename,
				imageData: base64Data,
				crc,
				originalFilename,
				mimeType: this.getMimeType(originalFilename),
			}
		} catch (error) {
			console.error(`Error processing image: ${error.message}`)
			throw error
		}
	}

	// Pobiera typ MIME na podstawie rozszerzenia pliku
	getMimeType(filename) {
		const extension = path.extname(filename).toLowerCase()
		const mimeTypes = {
			'.jpg': 'image/jpeg',
			'.jpeg': 'image/jpeg',
			'.png': 'image/png',
			'.gif': 'image/gif',
			'.bmp': 'image/bmp',
			'.webp': 'image/webp',
			'.svg': 'image/svg+xml',
		}

		return mimeTypes[extension] || 'application/octet-stream'
	}

	// Pobiera obraz z blockchain i zapisuje go tymczasowo
	async retrieveImageFromBlockchain(imageData, imageId) {
		try {
			// Dekoduj base64 do pliku
			const filePath = path.join(this.tempPath, imageId)
			await this.saveBase64Image(imageData, imageId)

			return filePath
		} catch (error) {
			console.error(`Error retrieving image from blockchain: ${error.message}`)
			throw error
		}
	}

	// Weryfikuje poprawność obrazu w blockchain
	async verifyBlockchainImage(imageData, storedCRC) {
		const calculatedCRC = calculateCRC(imageData)
		return calculatedCRC === storedCRC
	}
}

module.exports = new ImageProcessor()
