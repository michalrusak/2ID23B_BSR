const crc = require('crc')

/**
 * Oblicza sumę kontrolną CRC32 dla podanych danych
 * @param {string} data - Dane w formacie base64 lub string
 * @returns {string} - Suma kontrolna w formacie hex
 */
function calculateCRC(data) {
	// Oblicz CRC32 i zwróć jako string hex
	return crc.crc32(data).toString(16)
}

/**
 * Weryfikuje poprawność danych na podstawie sumy kontrolnej
 * @param {string} data - Dane do weryfikacji
 * @param {string} expectedCRC - Oczekiwana suma kontrolna
 * @returns {boolean} - True jeśli dane są poprawne
 */
function verifyCRC(data, expectedCRC) {
	const calculatedCRC = calculateCRC(data)
	return calculatedCRC === expectedCRC
}

module.exports = {
	calculateCRC,
	verifyCRC,
}
